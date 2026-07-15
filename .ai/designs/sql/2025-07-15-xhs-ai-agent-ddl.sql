-- =============================================
-- 需求: REQ-002 SQLite 数据库设计与初始化
-- 日期: 2025-07-15
-- 作者: honghui
-- 说明: 小红书AI内容智能体系统 SQLite 建表脚本
-- =============================================

-- 任务记录表
CREATE TABLE IF NOT EXISTS task_record (
    id TEXT PRIMARY KEY,
    keyword TEXT NOT NULL DEFAULT '',
    create_time TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    check_result TEXT NOT NULL DEFAULT '',
    cover_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_msg TEXT NOT NULL DEFAULT ''
);

-- 任务记录表索引
CREATE INDEX IF NOT EXISTS idx_task_record_keyword ON task_record(keyword);
CREATE INDEX IF NOT EXISTS idx_task_record_status ON task_record(status);
CREATE INDEX IF NOT EXISTS idx_task_record_create_time ON task_record(create_time);

-- 爆款素材库
CREATE TABLE IF NOT EXISTS hot_material (
    id TEXT PRIMARY KEY,
    keyword TEXT NOT NULL DEFAULT '',
    ref_title TEXT NOT NULL DEFAULT '',
    ref_content TEXT NOT NULL DEFAULT '',
    ref_tags TEXT NOT NULL DEFAULT '',
    like_num INTEGER NOT NULL DEFAULT 0,
    crawl_url TEXT NOT NULL DEFAULT '',
    crawl_time TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT ''
);

-- 爆款素材库索引
CREATE INDEX IF NOT EXISTS idx_hot_material_keyword ON hot_material(keyword);
CREATE INDEX IF NOT EXISTS idx_hot_material_task_id ON hot_material(task_id);
CREATE INDEX IF NOT EXISTS idx_hot_material_like_num ON hot_material(like_num);

-- 采集计数器（每日限制）
CREATE TABLE IF NOT EXISTS crawl_counter (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL DEFAULT '',
    count INTEGER NOT NULL DEFAULT 0
);

-- 采集计数器索引
CREATE INDEX IF NOT EXISTS idx_crawl_counter_date ON crawl_counter(date);
