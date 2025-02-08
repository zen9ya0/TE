import os
import tempfile
import shutil
import time
from datetime import datetime, timedelta
import logging
from threading import Thread
import schedule

class FileManager:
    def __init__(self, retention_minutes=60):
        self.base_dir = os.path.join(tempfile.gettempdir(), 'analytic_file')
        self.retention_minutes = retention_minutes
        self.setup_logging()
        
        # 確保目錄存在
        os.makedirs(self.base_dir, exist_ok=True)
        
        # 啟動清理排程
        self.start_cleanup_scheduler()
        
    def setup_logging(self):
        """設定日誌"""
        log_file = os.path.join(tempfile.gettempdir(), 'analytic_file_manager.log')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def save_file(self, file):
        """保存上傳的檔案到臨時目錄"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(self.base_dir, safe_filename)
            
            file.save(file_path)
            self.logger.info(f"檔案已保存: {file_path}")
            
            return {
                "filename": safe_filename,
                "path": file_path
            }
        except Exception as e:
            self.logger.error(f"保存檔案時發生錯誤: {str(e)}")
            raise

    def cleanup_old_files(self):
        """清理舊檔案"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=self.retention_minutes)
            count = 0
            
            for filename in os.listdir(self.base_dir):
                file_path = os.path.join(self.base_dir, filename)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_mtime < cutoff_time:
                    os.remove(file_path)
                    count += 1
                    self.logger.info(f"已刪除舊檔案: {file_path}")
            
            self.logger.info(f"清理完成，共刪除 {count} 個檔案")
        except Exception as e:
            self.logger.error(f"清理檔案時發生錯誤: {str(e)}")

    def start_cleanup_scheduler(self):
        """啟動定期清理排程"""
        def run_scheduler():
            schedule.every(1).minutes.do(self.cleanup_old_files)
            while True:
                schedule.run_pending()
                time.sleep(10)

        # 在背景執行排程
        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # 立即執行一次清理
        self.cleanup_old_files() 