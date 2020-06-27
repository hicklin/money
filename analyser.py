import pandas as pd
import matplotlib.pyplot as plt

f_data = pd.read_csv("a.csv", sep="\t", parse_dates=["date"])

f_data.plot(kind="scatter", x="date", y="paidIn")
plt.show()
