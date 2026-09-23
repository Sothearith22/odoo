"""Migrate subject teacher assignments from many-to-many to one teacher."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "SELECT to_regclass('public.university_subject') IS NOT NULL"
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        "ALTER TABLE university_subject "
        "ADD COLUMN IF NOT EXISTS teacher_id integer"
    )

    cr.execute(
        """
        UPDATE university_subject subject
           SET teacher_id = assignment.teacher_id
          FROM (
                SELECT DISTINCT ON (subject_id) subject_id, teacher_id
                  FROM university_teacher_subject_rel
                 ORDER BY subject_id, teacher_id
               ) assignment
         WHERE subject.id = assignment.subject_id
           AND subject.teacher_id IS NULL
        """
    )
    _logger.info(
        "Migrated %s subject teacher assignments to teacher_id",
        cr.rowcount,
    )
