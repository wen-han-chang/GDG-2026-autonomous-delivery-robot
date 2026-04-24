"""
拍照 + AprilTag 批次辨識測試腳本

用法:
  python capture_and_detect.py

功能:
  1. 從 ESP32-CAM 連拍 N 張照片存到 captures/ 資料夾
  2. 對所有照片跑 apriltag 辨識並印出結果
"""

import os
import time
import urllib.request
import urllib.error

import cv2
import numpy as np
import pupil_apriltags as apriltag

# ─── 設定 ────────────────────────────────────────────────────────
CAM_IP      = "10.247.168.157"
CAPTURE_URL = f"http://{CAM_IP}/capture"
NUM_PHOTOS  = 7          # 要拍幾張
INTERVAL    = 1.0        # 每張間隔秒數
OUTPUT_DIR  = "captures" # 儲存資料夾
TIMEOUT     = 15.0       # HTTP 逾時
# ────────────────────────────────────────────────────────────────

detector = apriltag.Detector(families="tag36h11")


def capture_photo(index: int) -> str | None:
    """從 ESP32-CAM 拍一張照片，存到 OUTPUT_DIR，回傳存檔路徑。"""
    try:
        with urllib.request.urlopen(CAPTURE_URL, timeout=TIMEOUT) as resp:
            data = resp.read()
        path = os.path.join(OUTPUT_DIR, f"capture_{index:03d}.jpg")
        with open(path, "wb") as f:
            f.write(data)
        print(f"[拍照] {path}  ({len(data)} bytes)")
        return path
    except urllib.error.URLError as e:
        print(f"[拍照失敗] {e}")
        return None


def detect_tags(image_path: str) -> list[int]:
    """對單張圖片跑 AprilTag 辨識，印出結果，回傳偵測到的 tag_id 列表。"""
    img = cv2.imread(image_path)
    if img is None:
        print(f"  [ERROR] 無法讀取 {image_path}")
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    results = detector.detect(gray)

    valid = [r for r in results if r.hamming <= 1]
    if not valid:
        print(f"  {os.path.basename(image_path)}: 未偵測到 tag")
    else:
        for r in valid:
            print(f"  {os.path.basename(image_path)}: tag_id={r.tag_id}  "
                  f"center=({r.center[0]:.0f}, {r.center[1]:.0f})  "
                  f"hamming={r.hamming}")
    return [r.tag_id for r in valid]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 拍照階段 ──────────────────────────────────────────────────
    print(f"=== 開始連拍 {NUM_PHOTOS} 張 ===")
    paths = []
    for i in range(NUM_PHOTOS):
        path = capture_photo(i)
        if path:
            paths.append(path)
        if i < NUM_PHOTOS - 1:
            time.sleep(INTERVAL)

    # ── 辨識階段 ──────────────────────────────────────────────────
    print(f"\n=== AprilTag 批次辨識（共 {len(paths)} 張）===")
    all_detections = []
    for path in paths:
        tag_ids = detect_tags(path)
        all_detections.extend(tag_ids)

    # ── 整合結論 ──────────────────────────────────────────────────
    print("\n=== 整合結論 ===")
    if not all_detections:
        print("結果：所有照片均未偵測到有效 AprilTag，請確認 tag 是否在鏡頭範圍內。")
    else:
        from collections import Counter
        counts = Counter(all_detections)
        most_common_id, most_common_count = counts.most_common(1)[0]
        total = len(all_detections)
        print(f"共偵測到 {total} 次有效 tag（來自 {len(paths)} 張照片）")
        for tag_id, count in sorted(counts.items()):
            print(f"  tag_id={tag_id}：出現 {count} 次")
        print(f"結論：最可能所在節點為 tag_id={most_common_id}（{most_common_count}/{len(paths)} 張確認）")

    print("\n完成。")


if __name__ == "__main__":
    main()
