import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarSlot, CalendarSlotStatus
from app.models.post import Post
from app.models.memory import MemoryLog
from app.models.strategy import Strategy
from app.schemas.runtime import TaskRuntimeContext
from app.services.content_agent import ContentAgent
from app.services.research_agent import ResearchAgent
from app.clients.integration_client import IntegrationServiceClient


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orchestrator evolution-agent.

    MVP: последовательно выполняет шаги:
      init → research (заглушка) → draft → validate (минимальная проверка) → save.
    Публикация в Telegram будет добавлена отдельно.
    """

    def __init__(
        self,
        db: AsyncSession,
        research_agent: Optional[ResearchAgent] = None,
        content_agent: Optional[ContentAgent] = None,
        integration_client: Optional[IntegrationServiceClient] = None,
        jwt_token: Optional[str] = None,
    ) -> None:
        self.db = db
        self.research_agent = research_agent or ResearchAgent()
        self.content_agent = content_agent or ContentAgent()
        self.integration_client = integration_client or IntegrationServiceClient()
        # JWT текущего пользователя или сервисный JWT для публикации
        self.jwt_token = jwt_token

    async def run_slot_generation(self, slot_id: str, user_id: int, feedback: Optional[str] = None) -> None:
        """
        Основной пайплайн генерации поста для слота.

        Пока вызывается синхронно (без Celery), но структура уже соответствует
        будущему `celery`-таску.
        """
        logger.info(f"🎯 evolution-agent: start generation for slot={slot_id}")

        slot = await self._load_and_lock_slot(slot_id, user_id)
        if not slot:
            logger.warning(f"evolution-agent: slot {slot_id} not found or not accessible")
            return

        # Загружаем связанную стратегию, чтобы пробросить persona и snapshot в контекст.
        strategy: Optional[Strategy] = None
        if slot.strategy_id:
            stmt = select(Strategy).where(
                Strategy.id == slot.strategy_id,
                Strategy.user_id == user_id,
            )
            res = await self.db.execute(stmt)
            strategy = res.scalar_one_or_none()

        persona = None
        strategy_snapshot = None
        if strategy is not None:
            try:
                persona = strategy.persona_json or None
            except Exception:
                persona = None
            # В snapshot кладём всё, что может пригодиться ContentAgent/валидации
            strategy_snapshot = {
                "persona": strategy.persona_json,
                "content_mix": strategy.content_mix_json,
                "schedule_rules": strategy.schedule_rules_json,
            }

        ctx = TaskRuntimeContext(
            task_id=uuid4(),
            user_id=user_id,
            channel_id=slot.channel_id,
            slot_id=slot.id,
            current_step="init",
            feedback=feedback,
            persona=persona,
            strategy_snapshot=strategy_snapshot,
        )

        try:
            # research
            ctx.current_step = "research"
            research_result = await self.research_agent.run_research(ctx)
            ctx.research_data = research_result.get("items", [])
            ctx.insights = research_result.get("insights", [])
            ctx.decisions_log.append("research_finished")

            # content draft + quality gate с ретраями
            validation_error: Optional[str] = None
            content_result: dict = {}

            for attempt in range(3):
                ctx.current_step = "draft"
                ctx.decisions_log.append(f"draft_attempt_{attempt + 1}")
                content_result = await self.content_agent.generate_post(ctx)
                ctx.draft_content = content_result.get("post_text", "") or ""

                ctx.current_step = "validate"
                validation_error = await self._validate_draft(ctx)
                if validation_error is None:
                    ctx.decisions_log.append("validation_passed")
                    break

                ctx.errors.append(validation_error)
                ctx.decisions_log.append(f"validation_failed_attempt_{attempt + 1}: {validation_error}")

            if validation_error is not None:
                raise ValueError(f"Validation failed after 3 attempts: {validation_error}")

            # save post
            ctx.current_step = "save"
            post = await self._save_post_and_update_slot(
                slot=slot,
                ctx=ctx,
                content_result=content_result,
            )

            # publish (через integration-service)
            ctx.current_step = "publish"
            await self._publish_post(post=post)

            ctx.current_step = "done"
            ctx.decisions_log.append("slot_completed_and_published")

            logger.info(
                f"✅ evolution-agent: generation completed for slot={slot_id}, user_id={user_id}"
            )
        except Exception as e:  # noqa: BLE001
            ctx.current_step = "error"
            ctx.errors.append(str(e))
            logger.error(
                f"❌ evolution-agent: error generating slot={slot_id}: {e}",
                exc_info=True,
            )
            await self._mark_slot_failed(slot)

    async def _load_and_lock_slot(
        self,
        slot_id: str,
        user_id: int,
    ) -> Optional[CalendarSlot]:
        stmt = select(CalendarSlot).where(
            CalendarSlot.id == slot_id,
            CalendarSlot.user_id == user_id,
        )
        res = await self.db.execute(stmt)
        slot: Optional[CalendarSlot] = res.scalar_one_or_none()
        if not slot:
            return None
        if slot.status != CalendarSlotStatus.PLANNED:
            logger.info(
                f"evolution-agent: slot {slot_id} has status={slot.status}, "
                "skipping generation",
            )
            return None

        slot.status = CalendarSlotStatus.PROCESSING
        slot.locked_by = "inline-orchestrator"
        slot.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(slot)
        return slot

    async def _save_post_and_update_slot(
        self,
        slot: CalendarSlot,
        ctx: TaskRuntimeContext,
        content_result: dict,
    ) -> Post:
        post = Post(
            user_id=ctx.user_id,
            channel_id=ctx.channel_id,
            slot_id=slot.id,
            content_text=content_result.get("post_text", ""),
            hashtags=content_result.get("hashtags", []),
            cta=content_result.get("cta"),
            meta_stats={
                "generated_at": datetime.utcnow().isoformat(),
                "model": "gpt-4o",
            },
        )
        self.db.add(post)

        slot.status = CalendarSlotStatus.READY
        slot.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def _validate_draft(self, ctx: TaskRuntimeContext) -> Optional[str]:
        """
        Простейший quality gate без ML.

        Проверяет:
        - минимальную длину;
        - отсутствие явных запрещённых тем из persona.forbidden_topics.
        """
        text = (ctx.draft_content or "").strip()
        if len(text) < 20:
            return "Generated post is too short"

        persona = ctx.persona or {}
        forbidden_topics = [str(t).lower() for t in persona.get("forbidden_topics", []) if t]
        text_lower = text.lower()
        for t in forbidden_topics:
            if t and t in text_lower:
                return f"Post contains forbidden topic: {t}"

        return None

    async def _mark_slot_failed(self, slot: CalendarSlot) -> None:
        slot.status = CalendarSlotStatus.FAILED
        slot.updated_at = datetime.utcnow()
        await self.db.commit()

    async def _publish_post(self, post: Post) -> None:
        """
        Публикация поста в Telegram через integration-service.

        Сейчас публикуем сразу после генерации, без дополнительного
        учёта времени слота (для MVP).
        """
        try:
            if not self.jwt_token:
                logger.info(
                    "evolution-agent: JWT токен не передан в Orchestrator, "
                    "пропускаем публикацию поста %s", post.id
                )
                return

            resp = await self.integration_client.send_telegram_message(
                jwt_token=self.jwt_token,
                text=post.content_text,
                channel_id=post.channel_id,
            )

            if isinstance(resp, dict) and resp.get("success"):
                post.telegram_message_id = resp.get("message_id")
                # Сохраняем базовый snapshot «памяти» о публикации в memory_logs
                memory_entry = MemoryLog(
                    user_id=post.user_id,
                    channel_id=post.channel_id,
                    post_id=post.id,
                    metrics_snapshot={
                        "published_at": datetime.utcnow().isoformat(),
                        "telegram_message_id": resp.get("message_id"),
                        "status": "published",
                    },
                )
                self.db.add(memory_entry)
                await self.db.commit()
                logger.info(
                    "✅ evolution-agent: post %s published to telegram channel %s, message_id=%s",
                    post.id,
                    post.channel_id,
                    resp.get("message_id"),
                )
            else:
                logger.error(
                    "❌ evolution-agent: failed to publish post %s, response=%s",
                    post.id,
                    resp,
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"evolution-agent: error publishing post {post.id}: {e}", exc_info=True)

