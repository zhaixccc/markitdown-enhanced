@echo off
echo 安装本地修改的MarkItDown包...
echo.

REM 卸载现有的markitdown包
echo 1. 卸载现有的markitdown包...
pip uninstall markitdown -y

REM 以开发模式安装本地包
echo.
echo 2. 以开发模式安装本地修改的包...
cd packages\markitdown
pip install -e .[all]

REM 返回原目录
cd ..\..

echo.
echo ✅ 安装完成！现在GUI将使用您修改的MarkItDown版本
echo.
echo 验证安装：
python -c "import markitdown; print(f'MarkItDown路径: {markitdown.__file__}')"

pause
