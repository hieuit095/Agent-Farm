with open('farm_agent/pr/manager.py') as f:
    content = f.read()

old_block = """            if any(term in stripped for term in allowed_terms):
                # Only check if it safely avoids danger terms
                if not any(
                    danger in stripped for danger in ["breaking", "release", "deploy", "migration"]
                ):
                    # Replace the first unmet checkbox
                    lines[i] = line.replace("[ ]", "[x]", 1)"""

new_block = """            if any(term in stripped for term in allowed_terms) and not any(
                danger in stripped for danger in ["breaking", "release", "deploy", "migration"]
            ):
                # Replace the first unmet checkbox
                lines[i] = line.replace("[ ]", "[x]", 1)"""

content = content.replace(old_block, new_block)

with open('farm_agent/pr/manager.py', 'w') as f:
    f.write(content)
