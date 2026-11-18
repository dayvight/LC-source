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

## 免责声明

本仓库仅聚合第三方开源项目的发布产物，不托管任何 IPA 文件。所有应用的版权与许可证归各自作者所有，安装前请自行确认来源可信。
