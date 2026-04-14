from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        data = self.rfile.read(length)
        with open('received.jpg', 'wb') as f:
            f.write(data)
        print(f"收到 {length} bytes，存成 received.jpg")
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # 關掉預設 log

print("等待 ESP32-CAM 傳圖，監聽 0.0.0.0:8080 ...")
HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
