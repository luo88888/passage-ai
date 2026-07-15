-- 文章表新增题材 / 语言风格 / 目标字数字段
-- 配合文章生成优化：弃用旧 style，改用 genre(题材) + language_style(语言风格) + word_count(字数,<=10000)
-- 旧 style 列保留不动，兼容存量数据，新流程不再写入/读取。

ALTER TABLE article
  ADD COLUMN genre         VARCHAR(20) NULL COMMENT '题材：news/knowledge/product/tutorial/opinion/story',
  ADD COLUMN languageStyle VARCHAR(20) NULL COMMENT '语言风格：professional/accessible/humorous/literary/formal',
  ADD COLUMN wordCount     INT         NULL COMMENT '目标字数（<=10000）';