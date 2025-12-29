"""创建示例Excel文件"""

import sys
import pandas as pd

def create_sample():
    """创建示例Excel文件"""
    df = pd.DataFrame({
        'question': [
            '请计算123 + 456 = ?',
            '北京是中国的首都吗？',
            '请用Python编写一个函数，返回斐波那契数列的前n项',
            '什么是机器学习？',
            '请解释一下什么是人工智能',
            '5的立方是多少？',
            '请列举5种编程语言',
            '地球到月球的距离大约是多少？',
            '请简述Python语言的特点',
            '什么是JSON格式？'
        ],
        'answer': [
            '579',
            '是',
            'def fibonacci(n): a, b = 0, 1; result = []; for _ in range(n): result.append(a); a, b = b, a + b; return result',
            '机器学习是人工智能的一个分支，通过算法让计算机从数据中学习并做出预测',
            '人工智能是让机器模拟人类智能的技术，包括学习、推理、感知等能力',
            '125',
            'Python, Java, JavaScript, C++, Go',
            '约38.4万公里',
            'Python是一种解释型、面向对象的编程语言，具有简洁的语法和强大的功能',
            'JSON是一种轻量级的数据交换格式，易于人阅读和编写，也易于机器解析和生成'
        ]
    })

    df.to_excel('questions.xlsx', index=False)
    print("示例Excel文件 'questions.xlsx' 已创建")
    print(f"包含 {len(df)} 条数据")

if __name__ == "__main__":
    create_sample()