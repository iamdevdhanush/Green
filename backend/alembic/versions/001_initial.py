"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])

    # Machines
    op.create_table(
        'machines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('mac_address', sa.String(17), nullable=False, unique=True),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('os_version', sa.String(255), nullable=True),
        sa.Column('cpu_info', sa.String(255), nullable=True),
        sa.Column('ram_gb', sa.Float(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('api_key', sa.String(64), nullable=False, unique=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='offline'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('idle_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_idle_hours', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_energy_kwh', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_co2_kg', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_cost_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_machines_mac_address', 'machines', ['mac_address'], unique=True)
    op.create_index('ix_machines_api_key', 'machines', ['api_key'], unique=True)
    op.create_index('ix_machines_status', 'machines', ['status'])
    op.create_index('ix_machines_hostname', 'machines', ['hostname'])

    # Energy Metrics
    op.create_table(
        'energy_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idle_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cpu_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('ram_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('energy_kwh', sa.Float(), nullable=False, server_default='0'),
        sa.Column('co2_kg', sa.Float(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_energy_machine_id', 'energy_metrics', ['machine_id'])
    op.create_index('ix_energy_recorded_at', 'energy_metrics', ['recorded_at'])

    # Shutdown Commands
    op.create_table(
        'shutdown_commands',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issued_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('idle_threshold_minutes', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_commands_machine_id', 'shutdown_commands', ['machine_id'])
    op.create_index('ix_commands_status', 'shutdown_commands', ['status'])

    # Audit Logs
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_machine_id', 'audit_logs', ['machine_id'])
    op.create_index('ix_audit_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_created_at', 'audit_logs', ['created_at'])

    # Monthly Analytics
    op.create_table(
        'monthly_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_kwh', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_co2_kg', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_cost_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_idle_hours', sa.Float(), nullable=False, server_default='0'),
        sa.Column('kwh_change_pct', sa.Float(), nullable=True),
        sa.Column('co2_change_pct', sa.Float(), nullable=True),
        sa.Column('cost_change_pct', sa.Float(), nullable=True),
        sa.Column('aggregated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('machine_id', 'year', 'month', name='uq_machine_month'),
    )
    op.create_index('ix_monthly_machine_id', 'monthly_analytics', ['machine_id'])
    op.create_index('ix_monthly_year_month', 'monthly_analytics', ['year', 'month'])


def downgrade() -> None:
    op.drop_table('monthly_analytics')
    op.drop_table('audit_logs')
    op.drop_table('shutdown_commands')
    op.drop_table('energy_metrics')
    op.drop_table('machines')
    op.drop_table('users')
