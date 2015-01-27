# Copyright 2014 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

# Initial operations for the Mellanox plugin

revision = '360e293103d2'
down_revision = '1f71e54a85e7'


from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'datacomnetwork',
        sa.Column('vid', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('name', sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint('vid'))

    op.create_table(
        'datacomport',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.Integer(), nullable=False, 
            autoincrement=False),
        sa.Column('port', sa.Integer(), nullable=True, autoincrement=False),
        sa.ForeignKeyConstraint(['network_id'], ['datacomnetwork.vid'], ),
        sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('datacomport')
    op.drop_table('datacomnetwork')
