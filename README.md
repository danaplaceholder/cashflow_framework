# cashflow

Computational graph framework for state-dependent incremental computation. 
- Monadic: ***Just create Nodes***. Can be nested.
    All dependency construction and data updates/management falls out automatically from Node relationships per input/output/created_by.
- Dynamic: Nodes can be created/deleted based on results from other Nodes. 
- Customizeable: Can use external data sources and manage updates via custom 
`get_last_modified` instance method
- Pull-based: Only run the Node you ask for and its upstream dependencies. 
- Visualize graph progression with automatically constructed mp4. 




```
docker compose run --rm dev
python src/cashflow/exampmle1.py 
```
...
```
...
Saved animation to /app/output_1784569497.mp4
```

