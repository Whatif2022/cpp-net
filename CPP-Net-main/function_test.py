import h5py
import  numpy as np
def main():
    path = "./data/sampling_matrix"
           #data = np.load(f"{path}/{self.ratio}_{self.block_size}.npy")
    with h5py.File(f"{path}/Sensing_Matrix_20_devide8_Normed.mat", 'r') as file:
        # 创建一个字典来存储所有变量
        data = [file[key][()] for key in file.keys()]  # 将所有数据存储在列表中
        # 如果需要将数据转换为 NumPy 数组，可以使用 np.array()
        #dimensions = data.shape
        # 提取第一个数组
        matrix_to_save = data[0] # 这里假设只提取第一个数组
        #matrix_to_save = matrix_to_save[:,0:819]  # 这里假设只提取第一个数组
        #matrix_to_save = matrix_to_save.T
        #npy_file_path = './data/sampling_matrix/Sensing_Matrix_20_devide8_Normed.npy' #保存路径
        #np.save(npy_file_path, matrix_to_save)
        dimensions = matrix_to_save.shape
        #print(matrix_to_save)  # 打印所有数据（无变量名）
        #print(dimensions)
    data1=np.load(f"{path}/Sensing_Matrix_20_devide8_Normed.npy")
    d1 = data1.shape
    print(d1)
if __name__ == "__main__":
    main()