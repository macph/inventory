from typing import Iterable

from django.db import connection

from .models import Item

ESTIMATED_DAYS_LEFT = """\
SELECT
    item_id,
    -- combined mean over time period with all gains set to zero then null
    nullif(
        sum(greatest(q0 - q1, 0)) / sum(extract(EPOCH FROM a1 - a0))::NUMERIC * 86400,
        0
    ) AS average
FROM (
    SELECT
        item_id,
        quantity AS q0,
        lead(quantity) OVER w0 AS q1,
        added AS a0,
        lead(added) OVER w0 AS a1
    FROM inventory_record
    WINDOW w0 AS (PARTITION BY item_id ORDER BY added)
) AS tr
GROUP BY item_id;
"""


def find_average_use(items: Iterable[Item]):
    ids = [i.id for i in items]
    with connection.cursor() as cursor:
        cursor.execute(ESTIMATED_DAYS_LEFT, [ids])
        result = {r[0]: r[1] for r in cursor.fetchall()}
    for i in items:
        i.average = result.get(i.id)
