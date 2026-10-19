import pandas as pd

df = pd.read_csv("shop_inventory.csv")

print("Columns:")
for i, col in enumerate(df.columns, 1): #print the column names of the csv file
    print(f"{i}. {col}")

col = input("\nSort by column name: ").strip() #input() is user input, strip() removes whitespaces, lower() converts the string to lowercase
order = input("Order (asc/desc): ").strip().lower() 

if col not in df.columns:
    print("Invalid column.")
else:
    df = df.sort_values(by=col, kind='quicksort',ascending=(order != "desc")) #sort the csv file by the column name and order specified by the user
    print(df.to_string(index=False)) #print the sorted dataframe without the index number