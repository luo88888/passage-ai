-- 文章表新增信息采集结果列（数据采集可视化，TODO 1.6）
-- 存储新闻题材 research 节点采集的结构化结果：{requirement, searchQueriesUsed, articles[]}
-- JSON 列，与现有 outline / images 列一致；ORM 用 Text 映射（见 models/article.py research_data）。
-- 注意：本脚本为手动执行（与 add_genre_fields.sql 等一致），重复执行会报列已存在，可忽略。

ALTER TABLE article
  ADD COLUMN researchData JSON NULL COMMENT '信息采集结果（JSON）：{requirement, searchQueriesUsed, articles[]}' AFTER enabledImageMethods;
