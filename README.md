# MovieMind - 豆瓣 Top 250 电影智能检索系统

## 项目简介

MovieMind 是一个基于 openGauss 数据库的电影信息管理系统，收录豆瓣 Top 250 经典电影，集成了 AI 智能推荐功能，帮助用户快速找到符合需求的电影。

## 核心功能

- 📊 **电影榜单浏览**: 展示 Top 250 电影，支持分页浏览
- 🔍 **多维度筛选**: 按类型、年代、评分等条件筛选电影
- 🤖 **AI 智能推荐**: 自然语言描述需求，AI 推荐最合适的电影
- 💬 **评论系统**: 查看电影评论和打分
- 📈 **数据可视化**: 年代分布、类型分布、评分分布图表

## 技术栈

### 后端
- **Web 框架**: Flask
- **数据库**: openGauss (PostgreSQL 兼容)
- **数据库驱动**: psycopg2
- **AI 集成**: DEEPSEEK API

### 前端
- **基础**: HTML5 + CSS3 + JavaScript
- **图表库**: Chart.js
- **设计**: 响应式设计，支持移动端

## 项目结构

```
final_project/
├── backend/                    # 后端代码
│   ├── app.py                 # Flask 主应用
│   ├── config.py              # 配置文件
│   ├── requirements.txt       # Python 依赖
│   └── .env.example          # 环境变量示例
├── database/                   # 数据库相关
│   ├── db_manager.py          # 数据库管理器
│   ├── init_db.py            # 数据库初始化脚本
│   └── import_data.py        # 数据导入脚本
├── frontend/                   # 前端代码
│   ├── index.html            # 主页面
│   ├── css/
│   │   └── style.css         # 样式文件
│   └── js/
│       └── app.js            # 前端逻辑
└── original_data/             # 原始数据
    ├── douban_movies.csv     # 电影信息
    └── comments.json         # 评论数据
```

## 快速开始

### 1. 环境准备

确保已安装:
- Python 3.8+
- openGauss 数据库 (运行在 Docker 中)

### 2. 配置数据库连接

复制 `.env.example` 为 `.env`，并修改数据库配置:

```bash
cd backend
copy .env.example .env
```

编辑 `.env` 文件，设置数据库连接信息:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=moviemind
DB_USER=gaussdb
DB_PASSWORD=Gaussdb@123
```

### 3. 安装 Python 依赖

```bash
cd backend
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
cd database
python init_db.py
```

### 5. 导入数据

```bash
python import_data.py
```

### 6. 启动后端服务

```bash
cd backend
python app.py
```

后端服务将运行在 `http://localhost:5000`

### 7. 启动前端

直接用浏览器打开 `frontend/index.html`，或使用 VS Code 的 Live Server 插件。

## 数据库设计

### 核心表结构

1. **user** - 用户表
2. **movie** - 电影表 (核心)
3. **celebrity** - 影人表 (导演/演员/编剧)
4. **genre** - 电影类型表
5. **movie_cast** - 电影-影人关联表 (M:N)
6. **movie_genre** - 电影-类型关联表 (M:N)
7. **review** - 评论/打分表
8. **chat_log** - AI 对话日志表

### ER 图关系

```
User (1) -----> (*) Review (*) <----- (1) Movie
                                         |
                         +---------------+---------------+
                         |                               |
                    (*) Movie_Cast (*)            (*) Movie_Genre (*)
                         |                               |
                    (1) Celebrity                   (1) Genre
```

## API 接口

### 电影相关
- `GET /api/movies` - 获取电影列表 (支持分页和筛选)
- `GET /api/movies/<id>` - 获取电影详情
- `GET /api/search?keyword=xxx` - 关键词搜索

### AI 功能
- `POST /api/ai-search` - AI 智能搜索

### 其他
- `GET /api/genres` - 获取所有类型
- `GET /api/celebrities` - 获取影人列表
- `GET /api/reviews/<movie_id>` - 获取电影评论
- `GET /api/stats` - 获取统计数据

## 开发说明

### 添加 DEEPSEEK API 支持

在 `.env` 文件中添加 API Key:

```env
DEEPSEEK_API_KEY=your-api-key-here
```

在 `db_manager.py` 的 `ai_search` 方法中集成 API 调用。

### 自定义数据导入

如果你的 CSV 格式不同，需要修改 `database/import_data.py` 中的字段映射。

## 注意事项

1. 确保 openGauss 数据库已启动并可连接
2. 首次运行需要先初始化数据库再导入数据
3. 前端直接打开 HTML 文件可能遇到 CORS 问题，建议使用 Live Server
4. AI 功能需要配置 DEEPSEEK API Key

## 下一步计划

- [ ] 完善 AI 自然语言处理逻辑
- [ ] 添加用户登录注册功能
- [ ] 实现用户收藏和评分功能
- [ ] 增加更多数据可视化图表
- [ ] 优化移动端体验

## 许可证

MIT License

## 作者

MovieMind Development Team
