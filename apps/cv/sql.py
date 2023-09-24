# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: sql.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-17 (y-m-d) 7:25 AM


def range_intersection_sql(tbname, bfname='begin', efname='end', pkname='id', tbname_alias='tbl') -> tuple[str, dict]:
    """
        Parameters that require sql :bv (value for bfname), :ev (value for efname)
        Prerequisites are begin value must be less then end or end value must be null
        Null value means infinity

        Result SQL should be like
        SELECT *
        FROM cv_cveducation as t
        WHERE (15 is null or t.id != 15) and
        (
            (
             '2023-05-05' < t.end and
             (CASE WHEN '2023-05-10' is null THEN true ELSE '2023-05-10' > t.begin END or '2023-05-10' is null)
            ) or (
             ('2023-05-05' < t.end or t.end is null) and
             CASE WHEN '2023-05-10' is null THEN true ELSE '2023-05-10' > t.begin END
            )
        )
    """
    sql = f'''SELECT * FROM {tbname} as {tbname_alias} 
WHERE (:pkv is null or {tbname_alias}.{pkname} != :pkv) and 
(( :bv < {tbname_alias}.{efname} and (CASE WHEN :ev is null THEN true ELSE :ev > {tbname_alias}.{bfname} END or :ev is null)) or 
( (:bv < {tbname_alias}.{efname} or {tbname_alias}.{efname} is null) and CASE WHEN :ev is null THEN true ELSE :ev > {tbname_alias}.{bfname} END ))'''

    return sql, {'pkv': None, 'bv': None, 'ev': None}


def end_is_null_for_sql(tbname, efname='end', pkname='id', tbname_alias='tbl') -> tuple[str, dict]:
    """
        Parameters that require sql :pkv (value for pkname) and :ev (value for efname)
        Prerequisite is end value must be null only for last one (most recent)
        Null value means infinity

        Probably, this sql for checking (constraint) has no sense (redundant) because
        range_intersection_sql will identify rows begin(2023-05-01)...end(null) and begin(2023-05-15)...end(null)
        as intersection. But, we will use it in check for ensure, better description and table integrity.
        Also, it can be used in other places.

        Result SQL should be like
        SELECT *
        FROM cv_cveducation as t
        WHERE (:pkv is null or t.id != :pkv) and (CASE WHEN :ev is not null THEN FALSE ELSE TRUE END and t.end is null)
        ORDER BY t.end DESC
    """
    sql = f'''SELECT * FROM {tbname} as {tbname_alias}
WHERE (:pkv is null or {tbname_alias}.{pkname} != :pkv) and
(CASE WHEN :ev is not null THEN FALSE ELSE TRUE END and {tbname_alias}.{efname} is null)
ORDER BY {tbname_alias}.{efname} DESC'''

    return sql, {'pkv': None, 'ev': None}


