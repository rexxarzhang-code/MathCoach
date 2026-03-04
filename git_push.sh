#!/bin/bash

# AI Math Coach - GitHub推送脚本
# 使用方法: chmod +x git_push.sh && ./git_push.sh

echo "🚀 准备推送 AI Math Coach 到 GitHub..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. 检查是否是Git仓库
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}📦 初始化 Git 仓库...${NC}"
    git init
    echo -e "${GREEN}✓ Git 仓库初始化完成${NC}"
    echo ""
else
    echo -e "${GREEN}✓ Git 仓库已存在${NC}"
    echo ""
fi

# 2. 添加远程仓库
echo -e "${YELLOW}🔗 配置远程仓库...${NC}"
if git remote | grep -q "origin"; then
    echo -e "${YELLOW}远程仓库已存在，更新URL...${NC}"
    git remote set-url origin https://github.com/rexxarzhang-code/MathCoach.git
else
    git remote add origin https://github.com/rexxarzhang-code/MathCoach.git
fi
echo -e "${GREEN}✓ 远程仓库配置完成${NC}"
echo ""

# 3. 检查暂存区
echo -e "${YELLOW}📋 检查文件状态...${NC}"
git status
echo ""

# 4. 添加所有文件
echo -e "${YELLOW}➕ 添加所有文件到暂存区...${NC}"
git add .
echo -e "${GREEN}✓ 文件添加完成${NC}"
echo ""

# 5. 显示将要提交的文件
echo -e "${YELLOW}📝 将要提交的文件：${NC}"
git status --short
echo ""

# 6. 确认提交
echo -e "${YELLOW}⚠️  请确认以下内容：${NC}"
echo "   1. .env 文件不在提交列表中"
echo "   2. venv/ 目录不在提交列表中"
echo "   3. 没有其他敏感信息"
echo ""
read -p "确认继续提交？(y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ 取消推送${NC}"
    exit 1
fi

# 7. 提交
echo ""
echo -e "${YELLOW}💾 提交更改...${NC}"
git commit -m "Initial commit: AI Math Coach with optimized PDF export

Features:
- AI-powered math error analysis (Qwen-VL & Gemini)
- Knowledge point analysis with curriculum mapping
- Error diagnosis with improvement suggestions
- Similar exercises generation from real exams
- Optimized PDF export with proper math symbols display
- Markdown export for digital archiving
- Configurable student profile and learning goals

Target users: Middle school students in Changsha, China
Focus: Preparing for top high schools (Yali, Changjun, etc.)"

echo -e "${GREEN}✓ 提交完成${NC}"
echo ""

# 8. 推送到GitHub
echo -e "${YELLOW}🚀 推送到 GitHub...${NC}"
echo ""

# 检查当前分支
CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    # 如果没有分支，创建main分支
    git branch -M main
    CURRENT_BRANCH="main"
fi

echo "当前分支: $CURRENT_BRANCH"
echo ""

# 推送
git push -u origin $CURRENT_BRANCH

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✨ 推送成功！${NC}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}🎉 下一步操作：${NC}"
    echo ""
    echo "1. 访问 GitHub 仓库："
    echo "   https://github.com/rexxarzhang-code/MathCoach"
    echo ""
    echo "2. 部署到 Streamlit Cloud："
    echo "   a. 访问 https://share.streamlit.io/"
    echo "   b. 点击 'New app'"
    echo "   c. 选择仓库: rexxarzhang-code/MathCoach"
    echo "   d. 分支: $CURRENT_BRANCH"
    echo "   e. 主文件: app.py"
    echo ""
    echo "3. 配置 Secrets（重要！）："
    echo "   在 Streamlit Cloud 的 Advanced settings -> Secrets 中添加："
    echo "   QWEN_API_KEY = \"你的千问API密钥\""
    echo "   GEMINI_API_KEY = \"你的Gemini API密钥\""
    echo ""
    echo "4. 部署完成后，记得更新 README.md 中的 App URL"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${GREEN}📚 参考文档：${NC}"
    echo "   - 部署指南: DEPLOYMENT.md"
    echo "   - 项目结构: docs/PROJECT_STRUCTURE.md"
    echo "   - 推送检查清单: PUSH_CHECKLIST.md"
    echo ""
else
    echo ""
    echo -e "${RED}❌ 推送失败！${NC}"
    echo ""
    echo "可能的原因："
    echo "1. 没有配置 Git 用户信息"
    echo "   解决: git config --global user.name '你的名字'"
    echo "         git config --global user.email '你的邮箱'"
    echo ""
    echo "2. 没有 GitHub 访问权限"
    echo "   解决: 使用 GitHub Personal Access Token"
    echo "         或配置 SSH 密钥"
    echo ""
    echo "3. 网络连接问题"
    echo "   解决: 检查网络连接"
    echo ""
    exit 1
fi
