import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarSlot, CalendarSlotStatus
from app.models.post import Post
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
    ) -> None:
        self.db = db
        self.research_agent = research_agent or ResearchAgent()
        self.content_agent = content_agent or ContentAgent()
        self.integration_client = integration_client or IntegrationServiceClient()

    async def run_slot_generation(self, slot_id: str, user_id: int) -> None:
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

        ctx = TaskRuntimeContext(
            task_id=uuid4(),
            user_id=user_id,
            channel_id=slot.channel_id,
            slot_id=slot.id,
            current_step="init",
        )

        try:
            # research
            ctx.current_step = "research"
            research_result = await self.research_agent.run_research(ctx)
            ctx.research_data = research_result.get("items", [])
            ctx.insights = research_result.get("insights", [])
            ctx.decisions_log.append("research_finished")

            # content draft
            ctx.current_step = "draft"
            content_result = await self.content_agent.generate_post(ctx)
            ctx.draft_content = content_result.get("post_text", "")
            ctx.decisions_log.append("draft_generated")

            # minimal validation
            ctx.current_step = "validate"
            if not ctx.draft_content or len(ctx.draft_content.strip()) < 20:
                raise ValueError("Generated post is too short")
            ctx.decisions_log.append("validation_passed")

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
            # В контексте evolution-agent мы не храним JWT, поэтому предполагаем,
            # что publish вызывается в контексте запроса пользователя через API‑gateway.
            # Здесь предполагается, что Orchestrator в будущем будет вызываться
            # из Celery с сервисным токеном и X-User-Id; пока publish оставляем
            # как no-op, чтобы не ломать пайплайн.
            #
            # TODO: при добавлении Celery передавать сервисный JWT и user_id,
            # затем вызывать self.integration_client.send_telegram_message(...).
            _ = post  # заглушка, чтобы не было предупреждения о неиспользуемой переменной
        except Exception as e:  # noqa: BLE001
            logger.error(f"evolution-agent: error publishing post {post.id}: {e}", exc_info=True)

