# 使用 Node.js 18
FROM node:22-alpine

# 設定工作目錄
WORKDIR /app

# 複製 package.json 安裝依賴
COPY package*.json ./
RUN npm install

# 複製前端程式碼
COPY . .

# 開放 Vite 預設 Port
EXPOSE 5173

# 啟動開發伺服器 (必須加上 --host 才能被外部存取)
CMD ["npm", "run", "dev", "--", "--host"]