import pandas as pd

dyad_list = [
    ('CHN', 'TWN'), ('CHN', 'JPN'), ('CHN', 'KOR'), ('CHN', 'PRK'),
    ('JPN', 'KOR'), ('JPN', 'PRK'), ('JPN', 'TWN'),
    ('KOR', 'PRK'), ('KOR', 'TWN'),
    ('PRK', 'TWN'),
    ('CHN', 'PHL'), ('CHN', 'VNM'),
]

data_list = []
for actor1, actor2 in dyad_list:
    print('='*66)
    print(f'正在讀取{actor1}_{actor2}2015_2025')
    filepath = f'data/raw/{actor1}_{actor2}2015_2025.csv'
    df = pd.read_csv(filepath, low_memory=False)
    df = df.drop(columns=['Unnamed: 0'])
    df['dyad'] = f'{actor1}-{actor2}'   
    data_list.append(df)
    print(f'{actor1}_{actor2}2015_2025合併成功')

final_df = pd.concat(data_list, ignore_index=True)
print(final_df.shape)
print(final_df['dyad'].value_counts())

final_df.to_csv('data/processed/gdelt_dyad.csv', index = False)
