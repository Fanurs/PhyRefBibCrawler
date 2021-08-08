# `phefbiler`
A simple bibtex crawler for physics references

## Usage
**Get bibtex from URL**
```python
import phefbiler as phb

url = 'https://journals.aps.org/pr/abstract/10.1103/PhysRev.105.1413'
bib = phb.get_bib(url)
print(bib)

# Out:
#-------------------------------------------------------------------------------
# @article{Wu_1957,
#     doi = {10.1103/physrev.105.1413},
#     url = {https://doi.org/10.1103%2Fphysrev.105.1413},
#     year = 1957,
#     month = {feb},
#     publisher = {American Physical Society ({APS})},
#     volume = {105},
#     number = {4},
#     pages = {1413--1415},
#     author = {C. S. Wu and E. Ambler and R. W. Hayward and D. D. Hoppes and R. P. Hudson},
#     title = {Experimental Test of Parity Conservation in Beta Decay},
#     journal = {Physical Review}
# }
```

**Reformat the bibtex**
```python
bibparser = phb.BibParser()
bibparser.read(string=bib)
bibparser.export_formatted_bibfile('formatted.bib')
with open('formatted.bib', 'r') as file:
    content = file.read()
print(content)

# Out:
#-------------------------------------------------------------------------------
# @article{Wu_1957,
#   title="{Experimental Test of Parity Conservation in Beta Decay}",
#   author={C. S. Wu and E. Ambler and R. W. Hayward and D. D. Hoppes and R. P. Hudson},
#   journal="{Physical Review}",
#   year={1957},
#   volume={105},
#   number={4},
#   pages={1413--1415},
#   doi={10.1103/physrev.105.1413},
# }
```
