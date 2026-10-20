import numpy as np
import pandas as pd

df = pd.read_csv('bike.csv')
#print(df.select_dtypes(exclude='float'))  # float를 제외한 모든 타입을 가진 칼럼 출력
df = df.set_index('datetime')
#print(df.head(25))
print(df.filter(like='10:00:00', axis=0))
print(df.filter(items=['weather', 'count']))
print(df.filter(regex='p..d'))