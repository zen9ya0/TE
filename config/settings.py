import os

# 伺服器設定
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080
DEBUG_MODE = False

# API 設定
API_KEY = "s2pNbV6HyN6UE26r7nK6Boa8UGmPmCKv"

# 檔案設定
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'exe', 'dll', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', '7z'}

# 確保上傳目錄存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER) 