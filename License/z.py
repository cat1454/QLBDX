import cv2
for b in [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]:
    for i in range(3):
        cap = cv2.VideoCapture(i, b)
        print("backend", b, "index", i, "=>", cap.isOpened())
        cap.release()