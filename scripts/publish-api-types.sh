#!/bin/bash
# 发布 ztools-api-types 到独立仓库的脚本

set -e

echo "📦 准备发布 ztools-api-types 到独立仓库..."

# 检查是否在 MTools 根目录
if [ ! -d "ztools-api-types" ]; then
  echo "❌ 错误：请在 MTools 根目录运行此脚本"
  exit 1
fi

# 获取远程仓库地址（需要先在 GitHub 创建）
REMOTE_URL="https://github.com/MToolsCenter/ztools-api-types.git"

echo "📍 目标仓库: $REMOTE_URL"
echo ""
echo "⚠️  请确保："
echo "   1. 已在 GitHub 创建私有仓库: MToolsCenter/ztools-api-types"
echo "   2. 仓库设置为 Private"
echo "   3. 没有初始化 README、.gitignore、license"
echo ""
read -p "按 Enter 继续，或 Ctrl+C 取消..."

# 检查 ztools-api-types 是否已提交到 MTools
if git diff --quiet ztools-api-types/ && git diff --cached --quiet ztools-api-types/; then
  echo "✅ ztools-api-types 已提交"
else
  echo "⚠️  ztools-api-types 有未提交的变更"
  read -p "是否先提交这些变更？(y/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    git add ztools-api-types/
    git commit -m "feat(ztools-api-types): prepare for publish"
  fi
fi

# 使用 git subtree 推送
echo "🚀 使用 git subtree 推送到远程仓库..."
git subtree push --prefix=ztools-api-types "$REMOTE_URL" main

echo ""
echo "✅ 发布完成！"
echo ""
echo "📝 下一步："
echo "   1. 访问 https://github.com/MToolsCenter/ztools-api-types"
echo "   2. 确认仓库设置为 Private"
echo "   3. 添加 README 和描述"
echo "   4. （可选）发布到 npm: cd 到该仓库 && npm publish"
