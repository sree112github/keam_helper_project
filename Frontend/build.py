import os
import re
import shutil

def minify_html(content):
    # Remove HTML comments except those starting with <!--[if (IE specific)
    content = re.sub(r'<!--(?!\[if).*?-->', '', content, flags=re.DOTALL)
    # Remove multiple spaces between tags
    content = re.sub(r'>\s+<', '><', content)
    # Collapse multiple blank lines
    content = re.sub(r'\n\s*\n', '\n', content)
    return content.strip()

def minify_css(content):
    # Remove CSS comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove whitespace around structural characters
    content = re.sub(r'\s*([\{\}\:\;\,])\s*', r'\1', content)
    # Remove newlines
    content = content.replace('\n', '')
    return content.strip()

def minify_js(content):
    # Remove block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove single line comments (but preserve URLs like http://)
    content = re.sub(r'(^|[\s;\}])//.*', r'\1', content, flags=re.MULTILINE)
    # Collapse multiple blank lines and spaces
    content = re.sub(r'\n\s*\n', '\n', content)
    return content.strip()

def build():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(src_dir, 'dist')

    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    # Process files
    files = ['index.html', 'style.css', 'script.js', 'firebase.json', 'robots.txt', 'sitemap.xml']
    
    for filename in files:
        src_path = os.path.join(src_dir, filename)
        dist_path = os.path.join(dist_dir, filename)
        
        if not os.path.exists(src_path):
            continue
            
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if filename.endswith('.html'):
            content = minify_html(content)
        elif filename.endswith('.css'):
            content = minify_css(content)
        elif filename.endswith('.js'):
            content = minify_js(content)
            
        # Write to dist
        with open(dist_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    print(f"Build complete. Minified files are in {dist_dir}")

if __name__ == '__main__':
    build()
