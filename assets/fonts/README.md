# 字体文件说明

## 所需字体

本项目封面生成功能需要中文字体文件用于 PIL 文字渲染。

**推荐字体：** 思源黑体（Source Han Sans CN）

## 下载方式

1. 访问 GitHub 官方仓库下载：
   https://github.com/adobe-fonts/source-han-sans/releases

2. 下载 `SourceHanSansCN-Regular.otf` 文件

3. 将字体文件放置到本目录：
   ```
   assets/fonts/SourceHanSansCN-Regular.otf
   ```

## 备选字体

如无法下载思源黑体，也可使用以下开源中文字体：

- 文泉驿微米黑：http://wenq.org/wqy2/index.cgi?action=browse&id=Home&lang=cn
- Noto Sans CJK SC：https://github.com/notofonts/noto-cjk

下载后重命名为 `SourceHanSansCN-Regular.otf` 或修改 `.env` 中的 `FONT_PATH` 配置指向实际字体文件。

## 注意事项

- 字体文件体积较大（约 10MB），已在 .gitignore 中排除，不会提交到 Git 仓库
- 首次使用前请确保字体文件已放置到位，否则封面文字叠加功能将失败
