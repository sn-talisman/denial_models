#!/usr/bin/env python3
"""Introspect the tebra PostgreSQL database and generate schema documentation."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

def get_db_connection():
    """Get database connection from environment variables."""
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/tebra"
    )
    
    # Parse connection string (handle both postgresql:// and postgresql+asyncpg://)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "")
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "")
    
    parts = db_url.split("@")
    if len(parts) == 2:
        auth, host_db = parts
        user, password = auth.split(":")
        host, db = host_db.split("/")
        if ":" in host:
            host, port = host.split(":")
        else:
            port = "5432"
    else:
        raise ValueError(f"Invalid DATABASE_URL format: {db_url}")
    
    return psycopg2.connect(
        host=host,
        port=port,
        database=db,
        user=user,
        password=password
    )

def introspect_schema():
    """Introspect database schema and return structured information."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    schema_info = {
        "tables": [],
        "views": [],
        "relationships": []
    }
    
    # Get all tables
    cursor.execute("""
        SELECT 
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        ORDER BY table_schema, table_name;
    """)
    
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table['table_name']
        schema = table['table_schema']
        full_name = f"{schema}.{table_name}" if schema != 'public' else table_name
        
        # Get columns
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default,
                udt_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position;
        """, (schema, table_name))
        
        columns = cursor.fetchall()
        
        # Get primary keys
        cursor.execute("""
            SELECT 
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s;
        """, (schema, table_name))
        
        pk_columns = [row['column_name'] for row in cursor.fetchall()]
        
        # Get foreign keys
        cursor.execute("""
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s;
        """, (schema, table_name))
        
        fks = cursor.fetchall()
        
        # Get indexes
        cursor.execute("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s;
        """, (schema, table_name))
        
        indexes = cursor.fetchall()
        
        table_info = {
            "schema": schema,
            "name": table_name,
            "full_name": full_name,
            "type": table['table_type'],
            "columns": [
                {
                    "name": col['column_name'],
                    "type": col['data_type'],
                    "udt_name": col['udt_name'],
                    "max_length": col['character_maximum_length'],
                    "nullable": col['is_nullable'] == 'YES',
                    "default": col['column_default']
                }
                for col in columns
            ],
            "primary_keys": pk_columns,
            "foreign_keys": [
                {
                    "column": fk['column_name'],
                    "references_table": f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}" if fk['foreign_table_schema'] != 'public' else fk['foreign_table_name'],
                    "references_column": fk['foreign_column_name']
                }
                for fk in fks
            ],
            "indexes": [{"name": idx['indexname'], "definition": idx['indexdef']} for idx in indexes]
        }
        
        if table['table_type'] == 'BASE TABLE':
            schema_info["tables"].append(table_info)
        else:
            schema_info["views"].append(table_info)
        
        # Store relationships
        for fk in fks:
            schema_info["relationships"].append({
                "from_table": full_name,
                "from_column": fk['column_name'],
                "to_table": f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}" if fk['foreign_table_schema'] != 'public' else fk['foreign_table_name'],
                "to_column": fk['foreign_column_name']
            })
    
    cursor.close()
    conn.close()
    
    return schema_info

def generate_markdown(schema_info):
    """Generate markdown documentation from schema info."""
    md = ["# Tebra Database Schema Documentation\n"]
    md.append(f"*Generated automatically from database introspection*\n\n")
    
    md.append("## Overview\n\n")
    md.append(f"- **Total Tables**: {len(schema_info['tables'])}\n")
    md.append(f"- **Total Views**: {len(schema_info['views'])}\n")
    md.append(f"- **Total Relationships**: {len(schema_info['relationships'])}\n\n")
    
    md.append("## Tables\n\n")
    
    for table in schema_info['tables']:
        md.append(f"### {table['full_name']}\n\n")
        md.append("### Columns\n\n")
        md.append("| Column Name | Data Type | Nullable | Default | Description |\n")
        md.append("|------------|-----------|----------|---------|-------------|\n")
        
        for col in table['columns']:
            nullable = "Yes" if col['nullable'] else "No"
            default = col['default'] or "-"
            max_len = f"({col['max_length']})" if col['max_length'] else ""
            md.append(f"| `{col['name']}` | {col['type']}{max_len} | {nullable} | {default} | |\n")
        
        if table['primary_keys']:
            md.append(f"\n**Primary Keys**: {', '.join(f'`{pk}`' for pk in table['primary_keys'])}\n\n")
        
        if table['foreign_keys']:
            md.append("**Foreign Keys**:\n\n")
            for fk in table['foreign_keys']:
                md.append(f"- `{fk['column']}` → `{fk['references_table']}.{fk['references_column']}`\n")
            md.append("\n")
        
        if table['indexes']:
            md.append("**Indexes**:\n\n")
            for idx in table['indexes']:
                md.append(f"- `{idx['name']}`: {idx['definition']}\n")
            md.append("\n")
        
        md.append("---\n\n")
    
    if schema_info['views']:
        md.append("## Views\n\n")
        for view in schema_info['views']:
            md.append(f"### {view['full_name']}\n\n")
            md.append("| Column Name | Data Type | Nullable |\n")
            md.append("|------------|-----------|----------|\n")
            for col in view['columns']:
                nullable = "Yes" if col['nullable'] else "No"
                md.append(f"| `{col['name']}` | {col['type']} | {nullable} |\n")
            md.append("\n---\n\n")
    
    md.append("## Entity Relationship Summary\n\n")
    md.append("### Key Entities (Inferred)\n\n")
    
    # Try to identify key entities
    table_names = [t['name'].lower() for t in schema_info['tables']]
    
    entities = {
        "Claims": [t for t in table_names if 'claim' in t],
        "Denials": [t for t in table_names if 'denial' in t or 'reject' in t],
        "Payers": [t for t in table_names if 'payer' in t or 'insurance' in t],
        "Practices": [t for t in table_names if 'practice' in t or 'organization' in t],
        "Patients": [t for t in table_names if 'patient' in t],
        "Providers": [t for t in table_names if 'provider' in t or 'physician' in t],
        "Procedures": [t for t in table_names if 'procedure' in t or 'cpt' in t or 'service' in t],
        "Diagnoses": [t for t in table_names if 'diagnosis' in t or 'icd' in t],
        "Remittance": [t for t in table_names if 'remittance' in t or 'era' in t or 'payment' in t]
    }
    
    for entity_type, matches in entities.items():
        if matches:
            md.append(f"- **{entity_type}**: {', '.join(matches)}\n")
    
    md.append("\n### Relationships\n\n")
    for rel in schema_info['relationships'][:20]:  # Limit to first 20 for readability
        md.append(f"- `{rel['from_table']}.{rel['from_column']}` → `{rel['to_table']}.{rel['to_column']}`\n")
    
    if len(schema_info['relationships']) > 20:
        md.append(f"\n*... and {len(schema_info['relationships']) - 20} more relationships*\n")
    
    return "\n".join(md)

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        
        # Load .env if it exists
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            # Try to load from current directory
            load_dotenv()
    except ImportError:
        print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
        print("Continuing without .env file...")
    
    try:
        print("Connecting to database...")
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            print(f"Using DATABASE_URL from environment (database: {db_url.split('/')[-1] if '/' in db_url else 'unknown'})")
        else:
            print("Warning: DATABASE_URL not set, using defaults")
        
        schema_info = introspect_schema()
        print(f"Found {len(schema_info['tables'])} tables and {len(schema_info['views'])} views")
        
        # Create docs directory if it doesn't exist
        docs_dir = Path(__file__).parent.parent / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        # Generate markdown
        md_content = generate_markdown(schema_info)
        
        # Write to file
        output_file = docs_dir / "database_schema.md"
        output_file.write_text(md_content)
        print(f"Schema documentation written to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

