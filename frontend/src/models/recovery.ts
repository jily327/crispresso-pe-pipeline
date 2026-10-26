import type { ErrorDetail, FieldValue } from './api';
export interface RecoveryView {
  recovery_contract: 'analysis-recovery-v1'; recovery_id: string; revision: number;
  workspace_label: string; classification: string; recovery_plan_sha256: string|null;
  scientific_identity_sha256: string|null; workflow_identity_sha256: string|null; analysis_mode: string|null;
  force_families: string[]; selected_force: string[]; closure: string[]; removal_paths: string[];
  stages: {stage_id:string;stage_kind:string;action:string;output_path:string;reason_codes:string[]}[];
  reasons: ErrorDetail[]; software:FieldValue[];backend:FieldValue[]; executable:boolean;
}
