# 使用 Python 3.11 輕量版
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製依賴清單並安裝 (利用 Docker Cache 加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# 開放 Port
EXPOSE 8000

# 啟動指令 (注意 host 要設為 0.0.0.0 才能被外部存取)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]