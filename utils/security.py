from upload_file_cli import upload_file_to_threat_prevention

class SecurityAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key

    def analyze_file(self, file_path):
        """執行檔案安全分析"""
        return upload_file_to_threat_prevention(self.api_key, file_path) 