# 物品申报审批系统

前后端分离的物品申报审批 Web 项目。所有用户身份平等：同一账号既可以提交物品申报，也可以审批**其他用户**提交的待审批申请，系统在后端强制禁止审批自己的申请。

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Vite + Element Plus + axios + vue-router |
| 后端 | FastAPI (Python 3.10+) |
| 数据库 | MySQL 5.7+ / 8.x（utf8mb4） |
| 安全 | 密码 bcrypt 加密、JWT Token 鉴权、图片类型与大小后端校验 |

## 项目结构

```
item-approval-system/
├── backend/
│   ├── main.py              # FastAPI 全部接口（认证/申报/审批/消息/图片上传）
│   ├── requirements.txt     # Python 依赖
│   └── uploads/images/      # 上传图片保存目录（自动创建，数据库只存路径）
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js       # 已配置 /api、/static 代理到 8000
│   └── src/
│       ├── main.js          # 入口（注册 Element Plus）
│       ├── App.vue          # 顶栏布局 + 未读数 4 秒轮询
│       ├── api/index.js     # axios 实例（Token 拦截器、401 跳转）
│       ├── router/index.js  # 路由 + 登录守卫
│       └── views/
│           ├── Login.vue           # 登录 / 注册页
│           ├── Home.vue            # 首页：申报表单 + 待我审批列表 + 审批弹窗
│           ├── MyApplications.vue  # 我的申请记录
│           ├── Messages.vue        # 我的消息（4 秒轮询、标记已读）
│           └── Friends.vue         # 我的好友（ID管理/搜索/添加/删除）
├── sql/
│   ├── init.sql             # 建库建表脚本（user / item_apply / message / friendship）
│   └── migrate_friends.sql  # 增量迁移脚本（已有库上添加好友功能）
└── tools/
    ├── cloudflared.exe          # 公网内网穿透工具
    ├── start-tunnel.bat         # 双击启动公网隧道
    └── add-firewall-rule.bat    # 双击放行 5173 防火墙端口（管理员）
```

## 一、导入数据库

确保本机已安装并启动 MySQL，然后任选一种方式执行脚本：

**方式 1：命令行**

```bash
mysql -u root -p < sql/init.sql
```

**方式 2：Navicat / DBeaver 等可视化工具**

打开 `sql/init.sql` 全选执行即可。脚本会自动创建数据库 `item_approval` 及 3 张表。

## 二、启动后端（FastAPI，端口 8000）

1. 进入后端目录：

```bash
cd backend
```

2. 创建并激活虚拟环境（Windows PowerShell 示例）：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
# 如提示脚本执行被禁止，可先执行：Set-ExecutionPolicy -Scope Process Bypass
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 配置数据库连接（默认值见 `main.py` 顶部，如你的 MySQL 密码不是 `root`，请通过环境变量修改）：

```powershell
# PowerShell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="你的MySQL密码"
$env:DB_NAME="item_approval"
```

```bash
# CMD
set DB_PASSWORD=你的MySQL密码
```

5. 启动服务：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动成功后：

- 接口文档（可在线调试）：http://localhost:8000/docs
- 上传图片访问地址：`http://localhost:8000/static/images/文件名`

## 三、启动前端（Vite，端口 5173）

新开一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：http://localhost:5173

> 没有 npm 环境请先安装 Node.js（建议 16+，自带 npm）。`vite.config.js` 已把 `/api`、`/static` 代理到 `http://localhost:8000`，无需额外处理跨域。

## 四、功能验证建议

1. 注册两个账号（如 `zhangsan`、`lisi`），密码均为 bcrypt 加密后入库。
2. 用 `zhangsan` 登录，在首页提交物品申报（名称/价格/描述/图片），提交后状态为 **待审批**。
3. `zhangsan` 的“待我审批”列表**看不到自己的申请**（前端不展示，后端接口也已排除本人）。
4. 退出后用 `lisi` 登录：首页“待我审批”可见该申请，点击【审批】：
   - 不填审批理由无法提交（前端拦截，后端同样返回 400）；
   - 选择【通过】或【驳回】并填写理由后提交。
5. 回到 `zhangsan`：
   - “我的申请记录”可看到状态、审批人、审批理由、审批时间；
   - 顶栏未读角标和“我的消息”页会出现审批通知（每 4 秒轮询），可单条或全部标记已读。
6. 安全验证：即使抓包/用 Postman 直接调 `POST /api/applications/{id}/review` 审批自己的申请，后端也返回 **“不允许审批自己提交的申请”**；不带 Token 调任何业务接口返回 401/403；上传非图片或超过 2MB 的文件会被后端拒绝。

## 五、手机访问与公网分享

前端已配置 `host: 0.0.0.0`、`allowedHosts: true`（见 `frontend/vite.config.js`），页面也做了手机窄屏适配，支持两种分享方式。

### 方式 A：同一 WiFi（局域网，不开外网也能访问）

1. 电脑上正常启动后端(8000)和前端(5173)。
2. Windows 防火墙需放行 5173 端口（仅首次，需管理员）。双击运行
   `tools/add-firewall-rule.bat`，在 UAC 弹窗点"是"即可（已添加则提示规则重复，无影响）。
3. 查看电脑 WLAN 局域网 IP（PowerShell 执行 `ipconfig`，找"无线局域网适配器 WLAN"的 IPv4 地址）。
   当前电脑的地址为 **`http://10.76.2.7:5173/`**（换网络后 IP 可能变化）。
4. 手机连**同一个 WiFi**，浏览器打开 `http://<电脑IP>:5173/` 即可。
   > 说明：页面里的 `/api`、`/static` 请求由电脑上的 Vite 自动转发给本机后端，手机只需能访问 5173 一个端口。

### 方式 B：全网访问（任何人、手机流量网络也能打开）

使用 Cloudflare 临时隧道（免费、无需注册账号），把本机 5173 通过一条公网 HTTPS 地址暴露出去：

1. 电脑上保持后端(8000)、前端(5173)运行。
2. 双击运行 `tools/start-tunnel.bat`（首次已内置下载好的 `tools/cloudflared.exe`，无需另装）。
3. 窗口日志中会出现一行公网地址，形如：
   `https://xxxx-xxxx-xxxx.trycloudflare.com`
   把它发给任何人，手机/电脑在任意网络下用浏览器打开即可直接使用（自带 HTTPS）。

当前会话已在运行的公网地址：**https://continental-picture-bulk-smooth.trycloudflare.com**

注意事项：

- **电脑必须保持开机且前后端与隧道进程都在运行**；电脑休眠/关机或关闭隧道窗口，公网地址立即失效。
- 临时隧道**每次重启域名都会变**；需要固定域名时可注册免费 Cloudflare 账号使用"命名隧道(named tunnel)"，或改用 ngrok / cpolar 绑定子域名，长期对外则建议购买云服务器部署。
- 该地址知道的人都能打开登录页，数据安全由账号注册/登录与 JWT 鉴权保证；分享范围请自行控制。

## 接口一览（均以 `/api` 开头，除注册登录外都需要 Token）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/applications` | 提交申报（multipart：名称/价格/描述/图片） |
| GET | `/api/applications/mine` | 我的申请记录 |
| GET | `/api/applications/pending` | 待我审批（后端自动排除本人 pending） |
| POST | `/api/applications/{id}/review` | 审批（action=approved/rejected，reason 必填；禁止自审） |
| GET | `/api/messages` | 我的消息列表 |
| GET | `/api/messages/unread-count` | 未读数 |
| POST | `/api/messages/{id}/read` | 标记单条已读 |
| POST | `/api/messages/read-all` | 全部已读 |
| PUT | `/api/user/uid` | 修改好友ID（后端唯一校验） |
| GET | `/api/users/search?q=xxx` | 通过好友ID搜索用户 |
| GET | `/api/friends` | 我的好友列表 |
| POST | `/api/friends/{userId}` | 添加好友（双向写入） |
| DELETE | `/api/friends/{userId}` | 删除好友（双向删除） |

## 六、好友功能

每个账号注册时系统自动生成 8 位唯一好友 ID（大写字母+数字），可在"我的好友"页面修改（后端强制唯一校验，与他人重复则拒绝）。

使用流程：
1. 用户 A 注册后获得好友 ID（如 `6OZ4C8CZ`），可在好友页面修改为自己的 ID。
2. 用户 B 在好友页面搜索 A 的好友 ID，找到后点击"加为好友"。
3. A 提交物品申报后，B 会在"我的消息"页面第一时间收到推送消息（"您的好友「A」提交了新的物品申报…"）。
4. 好友列表支持删除，删除后不再收到对方的申报推送。

> 好友推送与审批通知共用 `message` 表，通过 4 秒轮询获取，无需 WebSocket。

业务接口请求头携带：`Authorization: Bearer <登录返回的token>`
