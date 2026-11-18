# LC-source

个人自用的 AltStore / LiveContainer 软件源，收录 GitHub 上的开源 IPA 项目。

## 添加源

源地址（全部应用）：

```
https://raw.githubusercontent.com/dayvight/LC-source/refs/heads/main/all-apps.json
```

无法直连 GitHub 时，用镜像版（图标与 IPA 下载也走镜像）：

```
https://ghproxy.net/https://raw.githubusercontent.com/dayvight/LC-source/refs/heads/main/all-apps-proxy.json
```

镜像服务时有时无。若上述地址失效，可换任意 gh-proxy 类服务，只需把前缀换掉；或者在本地重新生成时用 `GH_PROXY=https://<新镜像>/ python3 scripts/build_source.py` 指定。

支持 AltStore、SideStore、LiveContainer、Feather 等兼容客户端。

## 当前收录

| 应用 | Bundle ID | 最低 iOS | 说明 |
| --- | --- | --- | --- |
| [Breeze](https://github.com/breeze-project-org/Breeze) | `com.zephyr.breeze` | 15.0 | Flutter 构建的漫画阅读器，插件化提供漫画源 |
| [OiiQT](https://github.com/gangz1o/OiiQT) | `com.gangz1o.oiiqt` | 18.0 | 在 iPhone / iPad 上管理 qBittorrent、Transmission 与 MoviePilot |
| [HGhubX](https://github.com/zxsos/HGhubX) | `com.hghubx.app` | 15.0 | 跨平台短剧客户端，Rust + Tauri 2 构建 |

每个应用也保留了独立的源，位于 `apps/<应用名>/apps.json`。

## 新增应用

1. 在 `apps.txt` 添加一行：

   ```
   <应用名> <owner/repo>
   ```

2. 新建 `apps/<应用名>/meta.json`（可选，用于覆盖自动猜测的信息）：

   ```json
   {
     "bundle": "com.example.app",
     "developer": "作者",
     "subtitle": "一句话简介",
     "description": "详细说明",
     "min_os": "16.0",
     "tint": "#3B82F6",
     "category": "utilities"
   }
   ```

3. 提交推送。Actions 会自动抓取 releases 并重建源。

如果 `apps/<应用名>/icon.png` 不存在，脚本会自动从最新的 IPA 里提取图标。

## 目录结构

```
apps.txt                     应用清单（唯一需要手动维护的列表）
apps/<应用名>/
  meta.json                  应用元数据（手写）
  icon.png                   图标（自动提取，可手动替换）
  apps.json                  生成的单应用源
  apps-proxy.json            同上，资源走 gh-proxy
all-apps.json                生成的总源
all-apps-proxy.json          总源的 gh-proxy 镜像
assets/icon.png              源图标
scripts/build_source.py      构建脚本
```

工作流每 6 小时自动运行一次，也可在 Actions 页面手动触发。

## 自动更新

上游发新版后，源会自动跟上，不需要手动做什么：

- **定时**：每 6 小时跑一次（UTC 0/6/12/18 点，即北京时间 08:00 / 14:00 / 20:00 / 02:00）
- **触发**：Actions 重新执行 `scripts/build_source.py` → 抓 `apps.txt` 里每个仓库的最新正式版 → 有变化就自动 commit `chore: refresh sources` 并推送
- **改配置也会触发**：`apps.txt`、`apps/<应用>/meta.json`、`apps/<应用>/icon.png`、构建脚本或工作流本身被修改时立即重建
- **手动**：Actions → Update source → Run workflow

两个需要注意的地方：

1. 公开仓库的定时工作流在**连续 60 天没有任何提交**后会被 GitHub 自动停用（会发邮件通知）。届时在 Actions 页面点一下重新启用即可。
2. `raw.githubusercontent.com` 有 CDN 缓存，推送后**大约 5 分钟内**客户端可能仍读到旧内容；LiveContainer 自身也会缓存源，需要在源页面下拉刷新。

已知限制：`bundleIdentifier` 和 `minOSVersion` 来自手写的 `meta.json`，不会在每次构建时重新解包 IPA 核对。上游哪天提高了最低系统版本，需要手动改 `meta.json`。

## 本地重建

```bash
GITHUB_TOKEN="$(gh auth token)" SOURCE_REPO=dayvight/LC-source python3 scripts/build_source.py
```

匿名调用 GitHub API 很容易撞上 403 rate limit，本地跑也建议带上 token。`SOURCE_REPO` 只影响生成文件里的 raw 链接，在 Actions 里由 `GITHUB_REPOSITORY` 自动提供。

## 版本策略

- 只保留最新正式版，不提供历史版本回退；需要回退能力时把 `MAX_VERSIONS` 调大（如 `MAX_VERSIONS=5`）
- 按版本号排序取最高版本，而不是按 release 创建时间
- 跳过 prerelease 和 draft
- 只收录 `.ipa` 资源，自动忽略 APK / DMG / EXE 等其它平台构建
- 版本号统一规范为纯数字（如 `v3.0.38` → `3.0.38`），因为 AltStore 要求如此

## 更新日志

每个版本的说明写进 `versions[].localizedDescription`，内容取自对应 GitHub release 的正文（`body`），自动做 markdown → 纯文本转换（去掉 `#`、`**`、表格、链接语法）并截断到 `MAX_CHANGELOG`（默认 1200 字符）。

用**纯文本**而不是 HTML 是有意为之：AltStore、SideStore、Feather 都是把 `localizedDescription` 直接塞进 text view，写 HTML 会原样显示标签。

客户端支持情况：

| 客户端 | 是否显示版本说明 |
| --- | --- |
| AltStore / SideStore | 显示（App 详情页「版本说明」+ 我的 App 更新提示） |
| Feather / Ksign / NexStore | 显示（Version History 页） |
| LiveContainer | **不显示**（源列表只有图标、名称、版本号，无详情页） |

所以这份日志主要是给「用 SideStore 装 Breeze」这类场景准备的。

## 免责声明

本仓库仅聚合第三方开源项目的发布产物，不托管任何 IPA 文件。所有应用的版权与许可证归各自作者所有，安装前请自行确认来源可信。
