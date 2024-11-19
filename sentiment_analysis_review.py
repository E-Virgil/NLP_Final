import pandas as pd

sen_ana = pd.read_csv('sentiment_analysis.csv')


print(sen_ana['Sentiment'].value_counts(normalize=True) * 100)