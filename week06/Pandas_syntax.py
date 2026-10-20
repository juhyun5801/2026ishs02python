import pandas as pd
import seaborn as sns

df = sns.load_dataset('penguins')
# print(df.head())
# print(df.tail())
# print(df.describe())
# print(df.info())

print(df.query('species.str.contains("hi")'))
print(df['species'].value_counts())

bl = int(input("Enter the amount of bill_length: "))
spcs = input("Enter the species: ")
print(df.query('bill_length_mm >= @bl and species == @spcs'))
