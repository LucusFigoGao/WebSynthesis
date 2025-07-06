#!/bin/bash

# 项目根目录（根据实际情况调整，如果脚本放在项目根目录可改为./）
PROJECT_ROOT="./"

# 检查config_files目录是否存在
if [ ! -d "${PROJECT_ROOT}/config_files" ]; then
    echo "错误：config_files目录不存在于${PROJECT_ROOT}"
    exit 1
fi

# 循环处理所有JSON配置文件
for config_file in "${PROJECT_ROOT}/config_files"/*.json; do
    # 提取文件名（不含路径和扩展名）作为index
    index=$(basename "${config_file}" .json)
    
    # 跳过非数字命名的文件
    if ! [[ "${index}" =~ ^[0-9]+$ ]]; then
        echo "跳过非数字索引文件: ${config_file}"
        continue
    fi
    
    echo "===================================="
    echo "开始处理 Task ${index}"
    echo "===================================="
    
    # 执行run.py命令，使用参考的参数配置
    python "${PROJECT_ROOT}/run.py" \
        --policy_method=gpt-4o \
        --reward_method=gpt-4o \
        --world_method=gpt-4o \
        --index="${index}"
    
    # 检查命令执行结果
    if [ $? -eq 0 ]; then
        echo "Task ${index} 处理完成"
    else
        echo "Task ${index} 处理失败"
    fi
    
    # 可选：添加延迟避免API请求过于频繁
    # sleep 5

done

echo "所有任务处理完毕"
