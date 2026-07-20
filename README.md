# Monadic Computational Graph Framework
Ideation and backend code 100% painstakingly and iteratively done by me, danaplaceholder. 
Visualization+drawing mostly done by ai, with guidance from danaplaceholder. 

# State-dependent incremental computation. 
- Monadic: ***Just create Nodes***. Can be nested.
    All dependency construction and data updates/management falls out automatically from Node relationships per input/output/created_by.
- Dynamic: Nodes can be created/deleted based on results from other Nodes. 
- Customizeable: Can use external data sources and manage updates via custom 
`get_last_modified` instance method
- Pull-based: Only run the Node you ask for and its upstream dependencies. 
- Visualize graph progression with automatically constructed mp4. 




```
docker compose run --rm dev
python src/cashflow/example1.py 
```
...
```
...
Saved animation to /app/output_1784569497.mp4
```

<img width="1415" height="733" alt="image" src="https://github.com/user-attachments/assets/5ce0d47d-02d7-4975-b3fc-e9367fdad6e2" />
