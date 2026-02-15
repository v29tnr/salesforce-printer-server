def prompt_user_for_input(prompt):
    return input(prompt)

def load_config(file_path):
    import toml
    return toml.load(file_path)

def save_config(file_path, config):
    import toml
    with open(file_path, 'w') as f:
        toml.dump(config, f)

def validate_zpl_content(zpl_content):
    if not isinstance(zpl_content, str):
        raise ValueError("ZPL content must be a string.")
    # Additional validation logic can be added here

def format_print_job(printer, job):
    return {
        'printer_id': printer.id,
        'job_id': job.id,
        'content': job.content,
        'is_zpl': job.is_zpl
    }

def print_job_summary(job):
    return f"Print Job ID: {job.id}, Printer ID: {job.printer_id}, Content Length: {len(job.content)}"