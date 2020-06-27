import pandas as pd
import matplotlib.pyplot as plt

f_data = pd.read_csv("f_data.csv", sep="\t", parse_dates=["date"], index_col="date")
f_data = f_data.sort_index()

f_data["paidIn"].dropna().cumsum().plot(kind="line")
f_data["paidOut"].dropna().cumsum().plot(kind="line")

#f_data["balance"].dropna().plot(kind="line")

plt.show()
