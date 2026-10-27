import seaborn as sns
import numpy as np
import pandas as pd
df = sns.load_dataset('titanic')
print(df.head())
print(df.info())
print(df.tail())
print(df.describe())

print(df['survived'].value_counts() )
print(df['alive'].value_counts() )
print(df['embark_town'].value_counts() )
print(df['embarked'].value_counts() )
print(df['pclass'].value_counts() )
print(df['class'].value_counts() )
df1 = df.drop(labels=['alive', 'class', 'embarked'], axis=1)
print(df1.info())
print(df.groupby('sex')['survived'].mean())
print(df1.groupby(['sex', 'pclass'])['survived'].mean())
print(df.groupby(['sex','pclass'])['survived'].agg(['mean','median','count']))
print(df.groupby(['sex','pclass'])[['survived','age']].agg({'survived':'mean', 'age':'max'}))


def get_IQR(data):
    _3rd = data.quantile(.75)
    _1st = data.quantile(.25)
    return (np.abs(_3rd - _1st) * 1.5)

df.groupby(['sex','pclass'])['age'].apply(get_IQR)


df = sns.load_dataset('penguins')
print(df.head())
print(df.info())

print(df.isna().sum())
print(df['species'].value_counts())

print(df.groupby('species')[['bill_length_mm','bill_depth_mm','flipper_length_mm','body_mass_g']].mean())
print(df.groupby('species')[['bill_length_mm','bill_depth_mm','flipper_length_mm','body_mass_g']].apply(lambda x: x.fillna(x.mean())))
print(df.head())
df=df.groupby('species')[['bill_length_mm','bill_depth_mm','flipper_length_mm','body_mass_g']].apply(lambda x: x.fillna(x.mean()))

from pathlib import Path
df2 = pd.read_csv(Path(__file__).resolve().parent / 'APPL_price' / 'APPL_price.csv')
print(df2.head())
print(df2.tail())
print(df2['Close'])
print(df2.info())

df2['Date'] = pd.to_datetime(df2['Date'])  # 문자열을 날짜로 변환
df2 = df2.set_index('Date')  # 날짜를 인덱스로 설정
print(df2.head())

print(df2['1980-12-13':'1980-12-18'])
print(df2['2022-06':'2022-06'])
print(df2.resample('7D').mean())

import pandas as pd
df3=pd.read_csv('Uber.csv')
print(df3.describe())
print(df3.head())
print(df3.info())
print(df3.tail())
df3['START_DATE*'] = pd.to_datetime(df3['START_DATE*'], errors='coerce')
print(df3['START_DATE*'])
df3['END_DATE*'] = pd.to_datetime(df3['END_DATE*'], errors='coerce')
print(df3.tail())
df3 = df3.sort_values(['START_DATE*','END_DATE*'])
print(df3['START_DATE*'].unique())
print(df3['END_DATE*'].unique())

print(df3['CATEGORY*'].value_counts())

print(df3['START*'].value_counts())

print(df3['STOP*'].value_counts())

print(df3['MILES*'].describe())
print(df3[df3['MILES*'] == df3['MILES*'].max()])

df3= df3.drop(1155)
print(df3['MILES*'].describe())

df3['DURATION*'] = (df3['END_DATE*'] - df3['START_DATE*']).dt.total_seconds() / 60
print(df3['DURATION*'])