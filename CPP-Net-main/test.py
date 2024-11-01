# %%
import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  #GPU编号 0为RTX A1000

import numpy as np
import glob
from time import time
import cv2
import torch
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
import argparse
from CPP import *  #导入外部定义函数cpp
from timm.models import create_model  #导入外部定义函数
import warnings
import lpips
import gc

warnings.filterwarnings("ignore")


def main(args):
    args = parser.parse_known_args()[0]

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu") #解析设备的GPU
    model = create_model(args.model, ratio=args.cs_ratio, pretrained=True) #使用 create_model 创建深度学习模型，并指定其名称和压缩感知比例 cs_ratio。模型是预训练的
    model = torch.nn.DataParallel(model) #允许多GPU运行
    model = model.to(device) #从CPU转化为GPU

    ext = {"/*.jpg", "/*.png", "/*.tif", "/*.bmp","/*.png"}
    filepaths = []
    test_name = args.dataset
    test_dir = os.path.join("./data", test_name)

    for img_type in ext:
        filepaths = filepaths + glob.glob(test_dir + img_type)

    result_dir = os.path.join(
        args.result_dir, args.model, test_name, str(args.cs_ratio)
    )
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)     #result_dir 指定结果保存的路径，包括模型名称、数据集名称和压缩感知比例。如果该目录不存在，则创建它。

    ImgNum = len(filepaths)   #测试图像数量
    PSNR_All, SSIM_All, LPIPS_ALL = [], [], []
    LPIPS = lpips.LPIPS(net="vgg").to(device)  #利用LPIPS计算感知相似度

    with torch.no_grad():
        print("\nCS Reconstruction Start")
        for img_no in range(ImgNum):
            imgName = filepaths[img_no] #一个RGB3通道变量 且维度为256*256*3

            Img = cv2.imread(imgName, 1)
            Img_yuv = cv2.cvtColor(Img, cv2.COLOR_BGR2YCrCb) #转化成YCrCb
            Img_rec_yuv = Img_yuv.copy()

            Iorg_y = Img_yuv[:, :, 0]
            [Iorg, row, col, Ipad, row_new, col_new] = imread_CS_py(Iorg_y, args) #使照片的行列数能被块整除
            Img_output = Ipad / 255.0

            batch_x = torch.from_numpy(Img_output)
            batch_x = batch_x.type(torch.FloatTensor)
            batch_x = batch_x.to(device)
            batch_x = batch_x.unsqueeze(0).unsqueeze(0)

            start = time()
            x_output = model(batch_x)
            end = time()

            x_output = x_output.squeeze(0).squeeze(0)
            Prediction_value = x_output.cpu().data.numpy()
            X_rec = np.clip(Prediction_value[:row, :col], 0, 1)

            rec_PSNR = psnr(Iorg.astype(np.float64), X_rec * 255, data_range=255)
            rec_SSIM = ssim(X_rec * 255, Iorg.astype(np.float64), data_range=255)

            rec_lpips = (
                LPIPS.forward(
                    torch.from_numpy(Iorg).float().to(device),
                    torch.from_numpy(X_rec * 255).float().to(device),
                )
                .cpu()
                .numpy()[0][0][0][0]
            )
            test_name_split = os.path.split(imgName)
            print(
                "[%02d/%02d] Run time for %s is %.4f, PSNR is %.2f, SSIM is %.4f, LPIPS is %.4f"
                % (
                    img_no,
                    ImgNum,
                    test_name_split[1],
                    (end - start),
                    rec_PSNR,
                    rec_SSIM,
                    rec_lpips,
                )
            )

            Img_rec_yuv[:, :, 0] = X_rec * 255
            im_rec_rgb = cv2.cvtColor(Img_rec_yuv, cv2.COLOR_YCrCb2BGR)
            im_rec_rgb = np.clip(im_rec_rgb, 0, 255).astype(np.uint8)
            resultName = "./%s/%s" % (result_dir, test_name_split[1])
            with open(os.path.join(result_dir, "results.csv"), "a+") as f:
                store_info = (
                    f"{resultName},{rec_PSNR},{rec_SSIM},{rec_lpips},{end - start}\n"
                )
                f.write(store_info)
            cv2.imwrite(
                "%s_ratio_%.2f_PSNR_%.2f_SSIM_%.4f_LPIPS_%.4f.png"
                % (resultName, args.cs_ratio, rec_PSNR, rec_SSIM, rec_lpips),
                im_rec_rgb,
            )
            del x_output

            PSNR_All.append(rec_PSNR)
            SSIM_All.append(rec_SSIM)
            LPIPS_ALL.append(rec_lpips)

            torch.cuda.empty_cache()
            gc.collect()

    print("\n")
    output_data = "CS ratio is %.2f, Avg PSNR/SSIM/LPIPS for %s is %.2f/%.4f/%.4f" % (
        args.cs_ratio,
        test_name,
        np.mean(PSNR_All),
        np.mean(SSIM_All),
        np.mean(LPIPS_ALL),
    )
    print(output_data)
    with open(os.path.join(result_dir, "results.csv"), "a+") as f:
        store_info = (
            f"avg, {np.mean(PSNR_All)}, {np.mean(SSIM_All)}, {np.mean(LPIPS_ALL)}\n"
        )
        f.write(store_info)
        store_info = f"avg, {np.mean(PSNR_All):.2f}, {np.mean(SSIM_All):.4f}, {np.mean(LPIPS_ALL):.4f}\n"
        f.write(store_info)
    print("CS Reconstruction End")


def imread_CS_py(Iorg, args):
    block_size = args.block_size
    [row, col] = Iorg.shape
    if np.mod(row, block_size) == 0:
        row_pad = 0
    else:
        row_pad = block_size - np.mod(row, block_size)
    if np.mod(col, block_size) == 0:
        col_pad = 0
    else:
        col_pad = block_size - np.mod(col, block_size)
    Ipad = np.concatenate((Iorg, np.zeros([row, col_pad])), axis=1)
    Ipad = np.concatenate((Ipad, np.zeros([row_pad, col + col_pad])), axis=0)
    [row_new, col_new] = Ipad.shape

    return [Iorg, row, col, Ipad, row_new, col_new]


if __name__ == "__main__": #只有当文件被直接运行才会执行下面代码
    parser = argparse.ArgumentParser()
    parser.add_argument("--cs_ratio", type=int, default=20, help="CS ratio") #CS radio从10调整为20
    parser.add_argument("--model", type=str, default="cpp8", help="model name")
    parser.add_argument(
        "--block_size", type=int, default=8, help="block size (default: 8)" #块大小从32调整为8 它到底有没有被分成8块
    )
    parser.add_argument(
        "--result_dir", type=str, default="results", help="result directory"
    )
    parser.add_argument(
        "--dataset", type=str, default="Set1", help="test dataset"
    )
    main(parser)
