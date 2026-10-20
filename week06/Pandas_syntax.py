import numpy as np
import pandas as pd
df = pd.read_csv('bike.csv')

df.rename({'registered':'registered_user','casual':'casual_user','temp':'temperature', 'atemp':'apparent_temperature'}, axis=1, inplace=True)
print(df.info())
print(df.describe(include='str'))  # 수치형 칼럼값이 아닌 문자열 칼럼이 낼 수 있는 요약 통계량
