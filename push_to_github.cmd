@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==== Day CarePlan len GitHub ====
where git >nul 2>nul || (echo Chua cai Git. Tai tai https://git-scm.com/download/win roi chay lai file nay. & pause & exit /b 1)
if exist .env (echo CANH BAO: co file .env chua key trong thu muc nay. Xoa no truoc khi day. & pause & exit /b 1)
set REPO=https://github.com/minh-tran-2611/careplan.git
echo Repo: %REPO%
if "%REPO%"=="" (echo Chua nhap link repo. & pause & exit /b 1)
if not exist .git git init -b main
git config user.name >nul 2>nul || git config user.name "Tran Nhat Minh"
git config user.email >nul 2>nul || git config user.email "minh-tran-2611@users.noreply.github.com"
git add -A
git commit -m "CarePlan: chatbot RAG + nhat ky + y lenh + bang ke hoach" || echo (Khong co thay doi moi de commit)
git branch -M main
git remote remove origin >nul 2>nul
git remote add origin %REPO%
git push -u origin main
if errorlevel 1 (echo Day len that bai. Kiem tra link repo va dang nhap GitHub. & pause & exit /b 1)
echo Xong! Quay lai Render de deploy.
pause
