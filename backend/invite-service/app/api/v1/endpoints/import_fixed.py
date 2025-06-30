# Патч для исправления функции import_targets_from_parsing
# Заменить строки 225-231 в import.py на:

            # Сначала коммитим новые цели
            await db.commit()
            
            # Затем обновляем счетчик целей в задаче (получаем реальный count из базы)
            count_query = select(InviteTarget).where(InviteTarget.task_id == task_id)
            count_result = await db.execute(count_query)
            all_targets = count_result.scalars().all()
            
            task.target_count = len(all_targets)
            task.updated_at = datetime.utcnow()
            
            await db.commit() 