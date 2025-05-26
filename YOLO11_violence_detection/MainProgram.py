# -*- coding: utf-8 -*-
import csv
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, \
    QMessageBox, QHeaderView, QTableWidgetItem, QAbstractItemView, QTableWidget, QVBoxLayout
import sys
import os
from PIL import ImageFont
from ultralytics import YOLO

sys.path.append('UIProgram')
from UIProgram.UiMain import Ui_MainWindow
import sys
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QCoreApplication
import detect_tools as tools
import cv2
import Config
from UIProgram.QssLoader import QSSLoader
from UIProgram.precess_bar import ProgressBar
import numpy as np
import urllib
import urllib.request
import hashlib
from datetime import datetime
# import torch
import chardet


def md5(str):
    import hashlib
    m = hashlib.md5()
    m.update(str.encode("utf8"))
    return m.hexdigest()


statusStr = {
    '0': '短信发送成功',
    '-1': '参数不全',
    '-2': '服务器空间不支持,请确认支持curl或者fsocket,联系您的空间商解决或者更换空间',
    '30': '密码错误',
    '40': '账号不存在',
    '41': '余额不足',
    '42': '账户已过期',
    '43': 'IP地址限制',
    '50': '内容含有敏感词'
}

smsapi = "http://api.smsbao.com/"
# 短信平台账号
user = 'dulan'
# 短信平台密码
password = md5('53afafab4d964fdc83e236fc12cf480e')
# 要发送的短信内容
content = '【VioLens】有特殊情况突发，请注意及时处理！'
# 要发送短信的手机号码
phone = '17859061512'


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(QMainWindow, self).__init__(parent)
        self.is_camera_open = None
        self.timer_camera = None
        self.model = None
        self.fontC = None
        self.img_width = None
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.initMain()
        self.signalconnect()
        self.model1_path = 'models/best1.pt'  # 图片检测模型
        self.model2_path = 'models/best2.pt'  # 视频检测模型
        self.is_table_shown = False  # 初始化标志，默认未显示表格

        # 加载css渲染效果
        style_file = 'UIProgram/style.css'
        qssStyleSheet = QSSLoader.read_qss_file(style_file)
        self.setStyleSheet(qssStyleSheet)

    def show_table_widget(self):
        if self.is_table_shown:
            # 移除表格并返回原来界面
            self.clear_table()
            self.is_table_shown = False
            return  # 直接返回

        # 自动检测文件编码
        with open('log.csv', 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']

        # 使用检测到的编码打开文件
        with open('log.csv', newline='', encoding=encoding) as csvfile:
            csv_data = list(csv.reader(csvfile))

        # 获取 CSV 数据的行数和列数
        row_count = len(csv_data) - 1  # 去掉表头
        column_count = len(csv_data[0])

        # 创建 QTableWidget
        table_widget = QTableWidget(row_count, column_count, self.ui.frame_2)

        # 设置表头
        headers = csv_data[0]
        table_widget.setHorizontalHeaderLabels(headers)

        # 填充表格内容
        for row in range(row_count):
            for column in range(column_count):
                item_text = csv_data[row + 1][column]  # row + 1 是为了跳过表头
                item = QTableWidgetItem(item_text)
                table_widget.setItem(row, column, item)

        # 检查 frame2 是否已有布局
        layout = self.ui.frame_2.layout()
        if layout is None:
            layout = QVBoxLayout(self.ui.frame_2)
            self.ui.frame_2.setLayout(layout)

        # 清除 frame2 中现有的部件
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 将 QTableWidget 添加到布局中
        layout.addWidget(table_widget)
        # 标记表格已经显示
        self.is_table_shown = True

    def clear_table(self):
        # 获取当前布局
        layout = self.ui.frame_2.layout()

        # 如果布局存在，清除所有子组件
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # 设置标志位为 False，表示表格已经被清除
        self.is_table_shown = False

    def signalconnect(self):
        self.ui.PicBtn.clicked.connect(self.open_img)
        self.ui.VideoBtn.clicked.connect(self.vedio_show)
        self.ui.CapBtn.clicked.connect(self.camera_show)
        self.ui.SaveBtn.clicked.connect(self.save_detect_video)
        self.ui.ExitBtn.clicked.connect(QCoreApplication.quit)
        self.ui.TabBtn.clicked.connect(self.show_table_widget)

        # 加载YOLO模型并进行预加载

    def load_model(self, model_path):

        print(f"Loading model from {model_path}")
        self.model = YOLO(model_path, task='detect')  # 使用YOLO类加载模型
        self.model(np.zeros((48, 48, 3)))  # 预先加载推理模型
        self.fontC = ImageFont.truetype("Font/platech.ttf", 25, 0)
        print("Model loaded and pre-inferred successfully.")

    def initMain(self):
        self.show_width = 770
        self.show_height = 480

        self.org_path = None

        self.is_camera_open = False
        self.cap = None

        # self.device = 0 if torch.cuda.is_available() else 'cpu'

        # 用于绘制不同颜色矩形框
        self.colors = tools.Colors()

        # 更新视频图像
        self.timer_camera = QTimer()

        # 更新检测信息表格
        # self.timer_info = QTimer()
        # 保存视频
        self.timer_save_video = QTimer()

        # 表格
        self.ui.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ui.tableWidget.verticalHeader().setDefaultSectionSize(40)
        self.ui.tableWidget.setColumnWidth(0, 80)  # 设置列宽
        self.ui.tableWidget.setColumnWidth(1, 200)
        self.ui.tableWidget.setColumnWidth(2, 150)
        self.ui.tableWidget.setColumnWidth(3, 90)
        self.ui.tableWidget.setColumnWidth(4, 230)
        # self.ui.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 表格铺满
        # self.ui.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        # self.ui.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 设置表格不可编辑
        self.ui.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)  # 设置表格整行选中
        self.ui.tableWidget.verticalHeader().setVisible(False)  # 隐藏列标题
        self.ui.tableWidget.setAlternatingRowColors(True)  # 表格背景交替

        # 设置主页背景图片border-image: url(:/icons/ui_imgs/icons/camera.png)
        # self.setStyleSheet("#MainWindow{background-image:url(:/bgs/ui_imgs/bg3.jpg)}")

    def open_img(self):
        if self.cap:
            # 打开图片前关闭摄像头
            self.video_stop()
            self.is_camera_open = False
            self.ui.CaplineEdit.setText('摄像头未开启')
            self.cap = None

        # 弹出的窗口名称：'打开图片'
        # 默认打开的目录：'./'
        # 只能打开.jpg, .jpeg, .png结尾的图片文件
        file_path, _ = QFileDialog.getOpenFileName(None, '打开图片', './', "Image files (*.jpg *.jpeg *.png)")
        if not file_path:
            return


        self.org_path = file_path
        self.org_img = tools.img_cvread(self.org_path)

        # 每次加载图片检测的模型（best1.pt）
        self.load_model(self.model1_path)

        # 目标检测
        t1 = time.time()
        self.results = self.model(self.org_path)[0]
        t2 = time.time()
        take_time_str = '{:.3f} s'.format(t2 - t1)
        self.ui.time_lb.setText(take_time_str)

        location_list = self.results.boxes.xyxy.tolist()
        cls_list = self.results.boxes.cls.tolist()
        conf_list = self.results.boxes.conf.tolist()

        # 筛选出置信度大于等于60%的检测框
        confidence_threshold = 0.60
        filtered_results = [
            (loc, cls, conf) for loc, cls, conf in zip(location_list, cls_list, conf_list)
            if conf >= confidence_threshold
        ]

        if filtered_results:
            print(123)
            # data = urllib.parse.urlencode({'u': user, 'p': password, 'm': phone, 'c': content})
            # send_url = smsapi + 'sms?' + data
            # response = urllib.request.urlopen(send_url)
            # the_page = response.read().decode('utf-8')
            # print(statusStr[the_page])
            # 如果存在满足条件的检测框，更新结果显示
            self.location_list = [list(map(int, loc)) for loc, _, _ in filtered_results]
            self.cls_list = [int(cls) for _, cls, _ in filtered_results]
            self.conf_list = ['%.2f %%' % (conf * 100) for _, _, conf in filtered_results]

            # 获取带有检测框的图像
            self.draw_img = self.results.plot()

            # 获取缩放后的图片尺寸并更新UI
            self.img_width, self.img_height = self.get_resize_size(self.draw_img)
            resize_cvimg = cv2.resize(self.draw_img, (self.img_width, self.img_height))
            pix_img = tools.cvimg_to_qpiximg(resize_cvimg)
            self.ui.label_show.setPixmap(pix_img)
            self.ui.label_show.setAlignment(Qt.AlignCenter)

            # 设置路径显示
            self.ui.PiclineEdit.setText(self.org_path)

            # 目标数目
            target_nums = len(self.cls_list)
            self.ui.label_nums.setText(str(target_nums))





            # 删除表格所有行并更新表格信息
            self.ui.tableWidget.setRowCount(0)
            self.ui.tableWidget.clearContents()
            self.tabel_info_show(self.location_list, self.cls_list, self.conf_list, path=self.org_path)

            # 保存图片到本地 violence 文件夹
            save_dir = './violence'
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            # 使用检测时间戳作为图片名称
            save_name = time.strftime('%Y%m%d_%H%M%S', time.localtime(t2)) + '.jpg'
            save_path = os.path.join(save_dir, save_name)

            # 保存图片
            cv2.imwrite(save_path, self.draw_img)

    def detact_batch_imgs(self):
        if self.cap:
            # 打开图片前关闭摄像头
            self.video_stop()
            self.is_camera_open = False
            self.ui.CaplineEdit.setText('摄像头未开启')
            self.cap = None
        directory = QFileDialog.getExistingDirectory(self,
                                                     "选取文件夹",
                                                     "./")  # 起始路径
        if not directory:
            return
        self.org_path = directory
        img_suffix = ['jpg', 'png', 'jpeg', 'bmp']
        for file_name in os.listdir(directory):
            full_path = os.path.join(directory, file_name)
            if os.path.isfile(full_path) and file_name.split('.')[-1].lower() in img_suffix:

                img_path = full_path
                self.org_img = tools.img_cvread(img_path)
                # 目标检测
                t1 = time.time()
                self.results = self.model(img_path)[0]
                t2 = time.time()
                take_time_str = '{:.3f} s'.format(t2 - t1)
                self.ui.time_lb.setText(take_time_str)

                location_list = self.results.boxes.xyxy.tolist()
                self.location_list = [list(map(int, e)) for e in location_list]
                cls_list = self.results.boxes.cls.tolist()
                self.cls_list = [int(i) for i in cls_list]
                self.conf_list = self.results.boxes.conf.tolist()
                self.conf_list = ['%.2f %%' % (each * 100) for each in self.conf_list]

                now_img = self.results.plot()

                self.draw_img = now_img
                # 获取缩放后的图片尺寸
                self.img_width, self.img_height = self.get_resize_size(now_img)
                resize_cvimg = cv2.resize(now_img, (self.img_width, self.img_height))
                pix_img = tools.cvimg_to_qpiximg(resize_cvimg)
                self.ui.label_show.setPixmap(pix_img)
                self.ui.label_show.setAlignment(Qt.AlignCenter)
                # 设置路径显示
                self.ui.PiclineEdit.setText(img_path)

                # 目标数目
                target_nums = len(self.cls_list)
                self.ui.label_nums.setText(str(target_nums))

                # 设置目标选择下拉框
                choose_list = ['全部']
                target_names = [Config.names[id] + '_' + str(index) for index, id in enumerate(self.cls_list)]
                choose_list = choose_list + target_names



                # # 删除表格所有行
                # self.ui.tableWidget.setRowCount(0)
                # self.ui.tableWidget.clearContents()
                self.tabel_info_show(self.location_list, self.cls_list, self.conf_list, path=img_path)
                self.ui.tableWidget.scrollToBottom()
                QApplication.processEvents()  # 刷新页面

    def draw_rect_and_tabel(self, results, img):
        now_img = img.copy()
        location_list = results.boxes.xyxy.tolist()
        self.location_list = [list(map(int, e)) for e in location_list]
        cls_list = results.boxes.cls.tolist()
        self.cls_list = [int(i) for i in cls_list]
        self.conf_list = results.boxes.conf.tolist()
        self.conf_list = ['%.2f %%' % (each * 100) for each in self.conf_list]

        for loacation, type_id, conf in zip(self.location_list, self.cls_list, self.conf_list):
            type_id = int(type_id)
            color = self.colors(int(type_id), True)
            # cv2.rectangle(now_img, (int(x1), int(y1)), (int(x2), int(y2)), colors(int(type_id), True), 3)
            now_img = tools.drawRectBox(now_img, loacation, Config.CH_names[type_id], self.fontC, color)

        # 获取缩放后的图片尺寸
        self.img_width, self.img_height = self.get_resize_size(now_img)
        resize_cvimg = cv2.resize(now_img, (self.img_width, self.img_height))
        pix_img = tools.cvimg_to_qpiximg(resize_cvimg)
        self.ui.label_show.setPixmap(pix_img)
        self.ui.label_show.setAlignment(Qt.AlignCenter)
        # 设置路径显示
        self.ui.PiclineEdit.setText(self.org_path)


        # 删除表格所有行
        self.ui.tableWidget.setRowCount(0)
        self.ui.tableWidget.clearContents()
        self.tabel_info_show(self.location_list, self.cls_list, self.conf_list, path=self.org_path)
        return now_img


    def get_video_path(self):
        file_path, _ = QFileDialog.getOpenFileName(None, '打开视频', './', "Image files (*.avi *.mp4 *.jepg *.png)")
        if not file_path:
            return None
        self.org_path = file_path
        self.ui.VideolineEdit.setText(file_path)
        return file_path

    def video_start(self):
        # 删除表格所有行
        self.ui.tableWidget.setRowCount(0)
        self.ui.tableWidget.clearContents()



        # 定时器开启，每隔一段时间，读取一帧
        self.timer_camera.start(1)
        self.timer_camera.timeout.connect(self.open_frame)

    def tabel_info_show(self, locations, clses, confs, path=None):
        log_entries = []  # 用于存储所有要写入日志的行

        for location, cls, conf in zip(locations, clses, confs):
            row_count = self.ui.tableWidget.rowCount()  # 返回当前行数(尾部)
            self.ui.tableWidget.insertRow(row_count)  # 尾部插入一行
            item_id = QTableWidgetItem(str(row_count + 1))  # 序号
            item_id.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # 设置文本居中
            item_path = QTableWidgetItem(str(path))  # 路径

            item_cls = QTableWidgetItem(str(Config.CH_names[cls]))
            item_cls.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # 设置文本居中

            item_conf = QTableWidgetItem(str(conf))
            item_conf.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # 设置文本居中

            item_location = QTableWidgetItem(str(location))  # 目标框位置

            self.ui.tableWidget.setItem(row_count, 0, item_id)
            self.ui.tableWidget.setItem(row_count, 1, item_path)
            self.ui.tableWidget.setItem(row_count, 2, item_cls)
            self.ui.tableWidget.setItem(row_count, 3, item_conf)
            self.ui.tableWidget.setItem(row_count, 4, item_location)

            # 获取当前时间并格式化为字符串
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 收集这一行的数据，并将当前时间附加到末尾，用于日志记录
            log_entry = [str(path), Config.CH_names[cls], str(conf), str(location), current_time]
            log_entries.append(log_entry)

        self.ui.tableWidget.scrollToBottom()

        # 调用 insert_rows 函数，将信息写入日志
        log_file_path = "log.csv"  # 可以根据需要指定路径或文件名
        tools.insert_rows(log_file_path, log_entries, ["序号", "路径", "类别", "置信度", "位置", "检测时间"])

    def video_stop(self):
        self.cap.release()
        self.timer_camera.stop()
        # self.timer_info.stop()

    import os

    def open_frame(self):
        # 去除跳帧功能，移除 frame_skip 和 frame_count 的相关代码
        self.video_ended = getattr(self, 'video_ended', False)  # 标记视频是否结束

        # 如果视频已经结束，保持最后一帧画面，不再进行任何更新
        if self.video_ended:
            if hasattr(self, 'last_img'):
                self.ui.label_show.setPixmap(self.last_img)
                self.ui.label_show.setAlignment(Qt.AlignCenter)
            return

        # 从视频中读取帧
        ret, now_img = self.cap.read()
        if ret:
            # 目标检测模型加载（仅加载一次）
            if not hasattr(self, 'model_loaded'):
                self.load_model(self.model2_path)
                self.model_loaded = True  # 标记模型已加载

            # 目标检测
            t1 = time.time()
            results = self.model(now_img)[0]
            t2 = time.time()
            take_time_str = '{:.3f} s'.format(t2 - t1)
            self.ui.time_lb.setText(take_time_str)

            # 提取检测结果
            location_list = results.boxes.xyxy.tolist()
            cls_list = results.boxes.cls.tolist()
            conf_list = results.boxes.conf.tolist()

            # 转换为适当的数据格式
            self.location_list = [list(map(int, e)) for e in location_list]
            self.cls_list = [int(i) for i in cls_list]
            self.conf_list = ['%.2f %%' % (each * 100) for each in conf_list]

            # 检测暴力类别并保存帧
            if location_list:  # 如果有检测到任何结果
                # 自定义绘制逻辑，如在检测结果中绘制边界框
                now_img = results.plot()

                # 更新UI表格并判断是否存在暴力类别
                self.tabel_info_show(self.location_list, self.cls_list, self.conf_list, path=self.org_path)

                # 检测“暴力”类别
                save_frame = any(Config.CH_names[cls] == '暴力' for cls in self.cls_list)

                # 如果检测到暴力，保存当前帧
                if save_frame:
                    save_dir = 'violence'
                    os.makedirs(save_dir, exist_ok=True)

                    file_name = f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    file_path = os.path.join(save_dir, file_name)

                    # 保存检测结果帧
                    cv2.imwrite(file_path, now_img)

            # 获取缩放后的图片尺寸并更新UI
            self.img_width, self.img_height = self.get_resize_size(now_img)
            resize_cvimg = cv2.resize(now_img, (self.img_width, self.img_height))
            pix_img = tools.cvimg_to_qpiximg(resize_cvimg)

            # 保持当前帧的图片作为最后一个显示的图片
            self.last_img = pix_img  # 保存最新的处理帧供后续显示

            # 更新UI画面，无论是否有检测结果
            self.ui.label_show.setPixmap(pix_img)
            self.ui.label_show.setAlignment(Qt.AlignCenter)

            # 更新其他UI元素，比如目标数目、置信度等
            target_nums = len(location_list)
            self.ui.label_nums.setText(str(target_nums))

            if target_nums >= 1:
                self.ui.type_lb.setText(Config.CH_names[int(cls_list[0])])
                self.ui.label_conf.setText(f'{conf_list[0] * 100:.2f} %%')
            else:
                self.ui.type_lb.setText('')
                self.ui.label_conf.setText('')

        else:
            # 视频帧读取结束，设置标记，停止继续读取
            self.video_ended = True
            if hasattr(self, 'last_img'):
                self.ui.label_show.setPixmap(self.last_img)
                self.ui.label_show.setAlignment(Qt.AlignCenter)

    def vedio_show(self):
        if self.is_camera_open:
            self.is_camera_open = False
            self.ui.CaplineEdit.setText('摄像头未开启')

        video_path = self.get_video_path()
        if not video_path:
            return None

        # 打开视频文件
        self.cap = cv2.VideoCapture(video_path)

        # 开始视频播放
        self.video_start()



    def vedio_show(self):
        if self.is_camera_open:
            self.is_camera_open = False
            self.ui.CaplineEdit.setText('摄像头未开启')

        video_path = self.get_video_path()
        if not video_path:
            return None
        self.cap = cv2.VideoCapture(video_path)
        self.video_start()


    def camera_show(self):
        self.is_camera_open = not self.is_camera_open
        if self.is_camera_open:
            self.ui.CaplineEdit.setText('摄像头开启')
            self.cap = cv2.VideoCapture(0)
            self.video_start()

        else:
            self.ui.CaplineEdit.setText('摄像头未开启')
            self.ui.label_show.setText('')
            if self.cap:
                self.cap.release()
                cv2.destroyAllWindows()
            self.ui.label_show.clear()

    def get_resize_size(self, img):
        _img = img.copy()
        img_height, img_width, depth = _img.shape
        ratio = img_width / img_height
        if ratio >= self.show_width / self.show_height:
            self.img_width = self.show_width
            self.img_height = int(self.img_width / ratio)
        else:
            self.img_height = self.show_height
            self.img_width = int(self.img_height * ratio)
        return self.img_width, self.img_height

    def save_detect_video(self):
        if self.cap is None and not self.org_path:
            QMessageBox.about(self, '提示', '当前没有可保存信息，请先打开图片或视频！')
            return

        if self.is_camera_open:
            QMessageBox.about(self, '提示', '摄像头视频无法保存!')
            return

        if self.cap:
            res = QMessageBox.information(self, '提示', '保存视频检测结果可能需要较长时间，请确认是否继续保存？',
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if res == QMessageBox.Yes:
                self.video_stop()
                self.btn2Thread_object = btn2Thread(self.org_path, self.model)
                self.btn2Thread_object.start()
                self.btn2Thread_object.update_ui_signal.connect(self.update_process_bar)
            else:
                return
        else:
            if os.path.isfile(self.org_path):
                fileName = os.path.basename(self.org_path)
                name, end_name = fileName.rsplit(".", 1)
                save_name = name + '_detect_result.' + end_name
                save_img_path = os.path.join(Config.save_path, save_name)
                # 保存图片
                cv2.imwrite(save_img_path, self.draw_img)
                QMessageBox.about(self, '提示', '图片保存成功!\n文件路径:{}'.format(save_img_path))
            else:
                img_suffix = ['jpg', 'png', 'jpeg', 'bmp']
                for file_name in os.listdir(self.org_path):
                    full_path = os.path.join(self.org_path, file_name)
                    if os.path.isfile(full_path) and file_name.split('.')[-1].lower() in img_suffix:
                        name, end_name = file_name.rsplit(".", 1)
                        save_name = name + '_detect_result.' + end_name
                        save_img_path = os.path.join(Config.save_path, save_name)
                        results = self.model(full_path)[0]
                        now_img = results.plot()
                        # 保存图片
                        cv2.imwrite(save_img_path, now_img)

                QMessageBox.about(self, '提示', '图片保存成功!\n文件路径:{}'.format(Config.save_path))

    def update_process_bar(self, cur_num, total):
        if cur_num == 1:
            self.progress_bar = ProgressBar(self)
            self.progress_bar.show()
        if cur_num >= total:
            self.progress_bar.close()
            QMessageBox.about(self, '提示', '视频保存成功!\n文件在{}目录下'.format(Config.save_path))
            return
        if self.progress_bar.isVisible() is False:
            # 点击取消保存时，终止进程
            self.btn2Thread_object.stop()
            return
        value = int(cur_num / total * 100)
        self.progress_bar.setValue(cur_num, total, value)
        QApplication.processEvents()


class btn2Thread(QThread):
    """
    进行检测后的视频保存
    """
    # 声明一个信号
    update_ui_signal = pyqtSignal(int, int)

    def __init__(self, path, model):
        super(btn2Thread, self).__init__()
        self.org_path = path
        self.model = model
        # 用于绘制不同颜色矩形框
        self.colors = tools.Colors()
        self.is_running = True  # 标志位，表示线程是否正在运行

    def run(self):
        # VideoCapture方法是cv2库提供的读取视频方法
        cap = cv2.VideoCapture(self.org_path)
        # 设置需要保存视频的格式“xvid”
        # 该参数是MPEG-4编码类型，文件名后缀为.avi
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        # 设置视频帧频
        fps = cap.get(cv2.CAP_PROP_FPS)
        # 设置视频大小
        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        # VideoWriter方法是cv2库提供的保存视频方法
        # 按照设置的格式来out输出
        fileName = os.path.basename(self.org_path)
        name, end_name = fileName.split('.')
        save_name = name + '_detect_result.avi'
        save_video_path = os.path.join(Config.save_path, save_name)
        out = cv2.VideoWriter(save_video_path, fourcc, fps, size)

        prop = cv2.CAP_PROP_FRAME_COUNT
        total = int(cap.get(prop))
        print("[INFO] 视频总帧数：{}".format(total))
        cur_num = 0

        # 确定视频打开并循环读取
        while (cap.isOpened() and self.is_running):
            cur_num += 1
            print('当前第{}帧，总帧数{}'.format(cur_num, total))
            # 逐帧读取，ret返回布尔值
            # 参数ret为True 或者False,代表有没有读取到图片
            # frame表示截取到一帧的图片
            ret, frame = cap.read()
            if ret == True:
                # 检测
                results = self.model(frame)[0]
                frame = results.plot()
                out.write(frame)
                self.update_ui_signal.emit(cur_num, total)
            else:
                break
        # 释放资源
        cap.release()
        out.release()

    def stop(self):
        self.is_running = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
