import os
from datetime import datetime
from werkzeug.utils import secure_filename

class FileHandler:
    def __init__(self, upload_folder, allowed_extensions):
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions

    def allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def get_file_count(self):
        return len([f for f in os.listdir(self.upload_folder) 
                   if os.path.isfile(os.path.join(self.upload_folder, f))])

    def handle_upload(self, request):
        if 'file' not in request.files:
            return {"error": "未找到上傳的檔案"}

        file = request.files['file']
        if file.filename == '':
            return {"error": "未提供檔案名稱"}

        if not self.allowed_file(file.filename):
            return {"error": "不支援的檔案類型"}

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(self.upload_folder, safe_filename)
        
        file.save(file_path)
        
        return {
            "filename": safe_filename,
            "path": file_path
        } 