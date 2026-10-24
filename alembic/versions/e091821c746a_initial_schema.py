from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e091821c746a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('tenants',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tenants_slug'), ['slug'], unique=True)

    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('audit_logs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=True),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('details_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_user_id'), ['user_id'], unique=False)

    op.create_table('cameras',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.Column('rtsp_url_encrypted', sa.String(length=1024), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('stream_fps', sa.Float(), nullable=False),
    sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cameras_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('experiment_runs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=True),
    sa.Column('experiment_name', sa.String(length=128), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=False),
    sa.Column('dataset_split', sa.String(length=64), nullable=False),
    sa.Column('score_threshold', sa.Float(), nullable=False),
    sa.Column('contrast_margin', sa.Float(), nullable=False),
    sa.Column('evaluation_protocol', sa.String(length=128), nullable=False),
    sa.Column('metadata_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('experiment_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_experiment_runs_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('tenant_memberships',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_user_membership')
    )
    with op.batch_alter_table('tenant_memberships', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tenant_memberships_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tenant_memberships_user_id'), ['user_id'], unique=False)

    op.create_table('workers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('staff_code', sa.String(length=64), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('batch', sa.String(length=64), nullable=True),
    sa.Column('department', sa.String(length=120), nullable=True),
    sa.Column('uniform_category', sa.String(length=64), nullable=True),
    sa.Column('enrollment_status', sa.String(length=32), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'staff_code', name='uq_tenant_worker_staff_code')
    )
    with op.batch_alter_table('workers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workers_staff_code'), ['staff_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_workers_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('camera_credentials',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('camera_id', sa.String(length=36), nullable=False),
    sa.Column('auth_type', sa.String(length=32), nullable=False),
    sa.Column('username', sa.String(length=120), nullable=True),
    sa.Column('encrypted_secret', sa.String(length=1024), nullable=False),
    sa.Column('kms_reference', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('camera_credentials', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_camera_credentials_camera_id'), ['camera_id'], unique=False)

    op.create_table('candidate_identities',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('candidate_code', sa.String(length=64), nullable=False),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('review_status', sa.String(length=32), nullable=False),
    sa.Column('approved_worker_id', sa.String(length=36), nullable=True),
    sa.Column('notes', sa.String(length=512), nullable=True),
    sa.Column('metadata_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_worker_id'], ['workers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'candidate_code', name='uq_tenant_candidate_code')
    )
    with op.batch_alter_table('candidate_identities', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_candidate_identities_candidate_code'), ['candidate_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_candidate_identities_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('enrollment_images',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('worker_id', sa.String(length=36), nullable=False),
    sa.Column('image_path', sa.String(length=512), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=True),
    sa.Column('blur_score', sa.Float(), nullable=False),
    sa.Column('quality_score', sa.Float(), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('enrollment_images', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_enrollment_images_worker_id'), ['worker_id'], unique=False)

    op.create_table('evaluation_results',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('experiment_run_id', sa.String(length=36), nullable=False),
    sa.Column('metric_name', sa.String(length=64), nullable=False),
    sa.Column('metric_value', sa.Float(), nullable=False),
    sa.Column('confidence_interval_low', sa.Float(), nullable=True),
    sa.Column('confidence_interval_high', sa.Float(), nullable=True),
    sa.Column('details_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['experiment_run_id'], ['experiment_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('evaluation_results', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evaluation_results_experiment_run_id'), ['experiment_run_id'], unique=False)

    op.create_table('video_assets',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('camera_id', sa.String(length=36), nullable=True),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('stored_path', sa.String(length=512), nullable=False),
    sa.Column('mime_type', sa.String(length=64), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('duration_seconds', sa.Float(), nullable=False),
    sa.Column('validation_status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('video_assets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_video_assets_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('person_embeddings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('worker_id', sa.String(length=36), nullable=True),
    sa.Column('candidate_identity_id', sa.String(length=36), nullable=True),
    sa.Column('enrollment_image_id', sa.String(length=36), nullable=True),
    sa.Column('observation_id', sa.String(length=36), nullable=True),
    sa.Column('embedding_vector', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('dimension', sa.Integer(), nullable=False),
    sa.Column('embedding_version', sa.String(length=32), nullable=False),
    sa.Column('model_version', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['candidate_identity_id'], ['candidate_identities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['enrollment_image_id'], ['enrollment_images.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('person_embeddings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_person_embeddings_candidate_identity_id'), ['candidate_identity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_person_embeddings_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_person_embeddings_worker_id'), ['worker_id'], unique=False)

    op.create_table('presence_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('worker_id', sa.String(length=36), nullable=True),
    sa.Column('candidate_identity_id', sa.String(length=36), nullable=True),
    sa.Column('identity_status', sa.String(length=32), nullable=False),
    sa.Column('session_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('session_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_currently_present', sa.Boolean(), nullable=False),
    sa.Column('last_seen_camera_id', sa.String(length=36), nullable=True),
    sa.Column('passage_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['candidate_identity_id'], ['candidate_identities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['last_seen_camera_id'], ['cameras.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('presence_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_presence_sessions_candidate_identity_id'), ['candidate_identity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_presence_sessions_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_presence_sessions_worker_id'), ['worker_id'], unique=False)

    op.create_table('video_jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('video_asset_id', sa.String(length=36), nullable=False),
    sa.Column('job_type', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('progress_percent', sa.Float(), nullable=False),
    sa.Column('error_details', sa.String(length=1024), nullable=True),
    sa.Column('summary_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('output_video_path', sa.String(length=512), nullable=True),
    sa.Column('output_crops_dir', sa.String(length=512), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_asset_id'], ['video_assets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('video_jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_video_jobs_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_video_jobs_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_video_jobs_video_asset_id'), ['video_asset_id'], unique=False)

    op.create_table('tracks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('video_job_id', sa.String(length=36), nullable=True),
    sa.Column('camera_id', sa.String(length=36), nullable=True),
    sa.Column('track_number', sa.Integer(), nullable=False),
    sa.Column('first_frame', sa.Integer(), nullable=False),
    sa.Column('last_frame', sa.Integer(), nullable=False),
    sa.Column('total_seen_frames', sa.Integer(), nullable=False),
    sa.Column('identity_status', sa.String(length=32), nullable=False),
    sa.Column('passage_status', sa.String(length=32), nullable=False),
    sa.Column('display_category', sa.String(length=32), nullable=False),
    sa.Column('candidate_identity_id', sa.String(length=36), nullable=True),
    sa.Column('matched_worker_id', sa.String(length=36), nullable=True),
    sa.Column('representative_crop_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['candidate_identity_id'], ['candidate_identities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['matched_worker_id'], ['workers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_job_id'], ['video_jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tracks_camera_id'), ['camera_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracks_candidate_identity_id'), ['candidate_identity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracks_matched_worker_id'), ['matched_worker_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracks_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracks_video_job_id'), ['video_job_id'], unique=False)

    op.create_table('observations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('track_id', sa.String(length=36), nullable=False),
    sa.Column('frame_idx', sa.Integer(), nullable=False),
    sa.Column('timestamp_offset_seconds', sa.Float(), nullable=False),
    sa.Column('bbox_x', sa.Integer(), nullable=False),
    sa.Column('bbox_y', sa.Integer(), nullable=False),
    sa.Column('bbox_w', sa.Integer(), nullable=False),
    sa.Column('bbox_h', sa.Integer(), nullable=False),
    sa.Column('detection_confidence', sa.Float(), nullable=False),
    sa.Column('quality_score', sa.Float(), nullable=False),
    sa.Column('blur_variance', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_observations_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_observations_track_id'), ['track_id'], unique=False)

    op.create_table('passage_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('camera_id', sa.String(length=36), nullable=True),
    sa.Column('video_job_id', sa.String(length=36), nullable=True),
    sa.Column('track_id', sa.String(length=36), nullable=True),
    sa.Column('worker_id', sa.String(length=36), nullable=True),
    sa.Column('candidate_identity_id', sa.String(length=36), nullable=True),
    sa.Column('identity_status', sa.String(length=32), nullable=False),
    sa.Column('passage_status', sa.String(length=32), nullable=False),
    sa.Column('display_category', sa.String(length=32), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('crop_path', sa.String(length=512), nullable=True),
    sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_reviewed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['candidate_identity_id'], ['candidate_identities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['video_job_id'], ['video_jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('passage_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_passage_events_camera_id'), ['camera_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_passage_events_candidate_identity_id'), ['candidate_identity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_passage_events_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_passage_events_track_id'), ['track_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_passage_events_video_job_id'), ['video_job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_passage_events_worker_id'), ['worker_id'], unique=False)

    op.create_table('match_decisions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('track_id', sa.String(length=36), nullable=True),
    sa.Column('observation_id', sa.String(length=36), nullable=True),
    sa.Column('top_candidate_id', sa.String(length=64), nullable=True),
    sa.Column('top_candidate_score', sa.Float(), nullable=False),
    sa.Column('runner_up_score', sa.Float(), nullable=False),
    sa.Column('score_margin', sa.Float(), nullable=False),
    sa.Column('score_threshold', sa.Float(), nullable=False),
    sa.Column('contrast_margin', sa.Float(), nullable=False),
    sa.Column('decision_category', sa.String(length=32), nullable=False),
    sa.Column('is_accepted', sa.Boolean(), nullable=False),
    sa.Column('rejection_reason', sa.String(length=255), nullable=True),
    sa.Column('model_version', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['observation_id'], ['observations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('match_decisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_match_decisions_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_match_decisions_track_id'), ['track_id'], unique=False)

    op.create_table('representative_crops',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('track_id', sa.String(length=36), nullable=True),
    sa.Column('passage_event_id', sa.String(length=36), nullable=True),
    sa.Column('worker_id', sa.String(length=36), nullable=True),
    sa.Column('candidate_identity_id', sa.String(length=36), nullable=True),
    sa.Column('file_path', sa.String(length=512), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('blur_score', sa.Float(), nullable=False),
    sa.Column('quality_score', sa.Float(), nullable=False),
    sa.Column('retention_status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['candidate_identity_id'], ['candidate_identities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['passage_event_id'], ['passage_events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('representative_crops', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_representative_crops_candidate_identity_id'), ['candidate_identity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_representative_crops_passage_event_id'), ['passage_event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_representative_crops_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_representative_crops_track_id'), ['track_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_representative_crops_worker_id'), ['worker_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('representative_crops', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_representative_crops_worker_id'))
        batch_op.drop_index(batch_op.f('ix_representative_crops_track_id'))
        batch_op.drop_index(batch_op.f('ix_representative_crops_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_representative_crops_passage_event_id'))
        batch_op.drop_index(batch_op.f('ix_representative_crops_candidate_identity_id'))

    op.drop_table('representative_crops')
    with op.batch_alter_table('match_decisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_match_decisions_track_id'))
        batch_op.drop_index(batch_op.f('ix_match_decisions_tenant_id'))

    op.drop_table('match_decisions')
    with op.batch_alter_table('passage_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_passage_events_worker_id'))
        batch_op.drop_index(batch_op.f('ix_passage_events_video_job_id'))
        batch_op.drop_index(batch_op.f('ix_passage_events_track_id'))
        batch_op.drop_index(batch_op.f('ix_passage_events_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_passage_events_candidate_identity_id'))
        batch_op.drop_index(batch_op.f('ix_passage_events_camera_id'))

    op.drop_table('passage_events')
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_observations_track_id'))
        batch_op.drop_index(batch_op.f('ix_observations_tenant_id'))

    op.drop_table('observations')
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tracks_video_job_id'))
        batch_op.drop_index(batch_op.f('ix_tracks_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_tracks_matched_worker_id'))
        batch_op.drop_index(batch_op.f('ix_tracks_candidate_identity_id'))
        batch_op.drop_index(batch_op.f('ix_tracks_camera_id'))

    op.drop_table('tracks')
    with op.batch_alter_table('video_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_video_jobs_video_asset_id'))
        batch_op.drop_index(batch_op.f('ix_video_jobs_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_video_jobs_status'))

    op.drop_table('video_jobs')
    with op.batch_alter_table('presence_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_presence_sessions_worker_id'))
        batch_op.drop_index(batch_op.f('ix_presence_sessions_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_presence_sessions_candidate_identity_id'))

    op.drop_table('presence_sessions')
    with op.batch_alter_table('person_embeddings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_person_embeddings_worker_id'))
        batch_op.drop_index(batch_op.f('ix_person_embeddings_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_person_embeddings_candidate_identity_id'))

    op.drop_table('person_embeddings')
    with op.batch_alter_table('video_assets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_video_assets_tenant_id'))

    op.drop_table('video_assets')
    with op.batch_alter_table('evaluation_results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evaluation_results_experiment_run_id'))

    op.drop_table('evaluation_results')
    with op.batch_alter_table('enrollment_images', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_enrollment_images_worker_id'))

    op.drop_table('enrollment_images')
    with op.batch_alter_table('candidate_identities', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_candidate_identities_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_candidate_identities_candidate_code'))

    op.drop_table('candidate_identities')
    with op.batch_alter_table('camera_credentials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_camera_credentials_camera_id'))

    op.drop_table('camera_credentials')
    with op.batch_alter_table('workers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workers_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_workers_staff_code'))

    op.drop_table('workers')
    with op.batch_alter_table('tenant_memberships', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tenant_memberships_user_id'))
        batch_op.drop_index(batch_op.f('ix_tenant_memberships_tenant_id'))

    op.drop_table('tenant_memberships')
    with op.batch_alter_table('experiment_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_experiment_runs_tenant_id'))

    op.drop_table('experiment_runs')
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cameras_tenant_id'))

    op.drop_table('cameras')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_tenant_id'))

    op.drop_table('audit_logs')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tenants_slug'))

    op.drop_table('tenants')
