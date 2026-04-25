import re

# Fix Dashboard.tsx
with open('frontend/src/pages/Dashboard.tsx', 'r', encoding='utf-8') as f:
    d = f.read()

# Insert missing </div> after logo section before controls
d = d.replace(
    '          </div>\n\n        <div className="flex items-center gap-2">',
    '          </div>\n        </div>\n\n        <div className="flex items-center gap-2">'
)

with open('frontend/src/pages/Dashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(d)
print('Fixed Dashboard.tsx')

# Fix Home.tsx if needed
with open('frontend/src/pages/Home.tsx', 'r', encoding='utf-8') as f:
    h = f.read()

if '      </div>\n  );' in h:
    h = h.replace('      </div>\n  );', '      </div>\n    </div>\n  );')
    with open('frontend/src/pages/Home.tsx', 'w', encoding='utf-8') as f:
        f.write(h)
    print('Fixed Home.tsx')
else:
    print('Home.tsx OK or different pattern')
