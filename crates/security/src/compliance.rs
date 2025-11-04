use coderabbit_shared::{Result, CodeRabbitError};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;


#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SOC2Control {
    pub control_id: String,
    pub control_name: String,
    pub control_type: SOC2ControlType,
    pub description: String,
    pub status: ControlStatus,
    pub evidence: Vec<ControlEvidence>,
    pub last_assessment: Option<chrono::DateTime<chrono::Utc>>,
    pub next_assessment: Option<chrono::DateTime<chrono::Utc>>,
    pub owner: String,
    pub maturity_level: u8, // 1-5 scale
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlEvidence {
    pub evidence_id: String,
    pub evidence_type: EvidenceType,
    pub description: String,
    pub file_path: Option<String>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub collected_by: String,
    pub automated: bool,
    pub validity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SOC2ControlType {
    Security,
    Availability,
    ProcessingIntegrity,
    Confidentiality,
    Privacy,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ControlStatus {
    NotImplemented,
    PartiallyImplemented,
    Implemented,
    UnderReview,
    NonCompliant,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EvidenceType {
    ConfigurationSnapshot,
    AuditLog,
    PenetrationTest,
    VulnerabilityScan,
    PolicyDocument,
    TrainingRecord,
    IncidentReport,
    MonitoringDashboard,
    CodeReview,
    AccessControlTest,
}

#[derive(Debug)]
pub struct ComplianceManager {
    controls: Arc<RwLock<HashMap<String, SOC2Control>>>,
    audit_logs: Arc<RwLock<Vec<AuditLogEntry>>>,
    evidence_store: Arc<RwLock<HashMap<String, ControlEvidence>>>,
    compliance_stats: Arc<RwLock<ComplianceStats>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub entry_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub user_id: String,
    pub action: String,
    pub resource: String,
    pub outcome: AuditOutcome,
    pub ip_address: Option<String>,
    pub user_agent: Option<String>,
    pub details: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AuditOutcome {
    Success,
    Failure,
    Unauthorized,
    Timeout,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceStats {
    pub total_controls: u64,
    pub implemented_controls: u64,
    pub compliance_score: f32,
    pub last_audit: Option<chrono::DateTime<chrono::Utc>>,
    pub critical_findings: u64,
    pub medium_findings: u64,
    pub low_findings: u64,
    pub automated_controls_percentage: f32,
}

impl ComplianceManager {
    pub async fn new() -> Result<Self> {
        tracing::info!("Initializing SOC 2 Type II compliance manager");
        
        let manager = Self {
            controls: Arc::new(RwLock::new(HashMap::new())),
            audit_logs: Arc::new(RwLock::new(Vec::new())),
            evidence_store: Arc::new(RwLock::new(HashMap::new())),
            compliance_stats: Arc::new(RwLock::new(ComplianceStats {
                total_controls: 0,
                implemented_controls: 0,
                compliance_score: 0.0,
                last_audit: None,
                critical_findings: 0,
                medium_findings: 0,
                low_findings: 0,
                automated_controls_percentage: 0.0,
            })),
        };
        
        manager.initialize_default_controls().await?;
        
        Ok(manager)
    }

    /// Initialize default SOC 2 controls
    async fn initialize_default_controls(&self) -> Result<()> {
        tracing::info!("Initializing default SOC 2 Type II controls");
        
        let default_controls = vec![
            // Security Controls
            self.create_security_control(
                "CC6.1",
                "Logical Access Security",
                "Logical access security measures are implemented to protect against threats from sources outside the system.",
                "system",
            ),
            self.create_security_control(
                "CC6.2",
                "User Access Provisioning",
                "User access is provisioned through a formal process that includes authorization and periodic review.",
                "system",
            ),
            self.create_security_control(
                "CC6.6",
                "Logical Access Controls",
                "Logical access controls are implemented to restrict access to authorized users and processes.",
                "system",
            ),
            
            // Availability Controls
            self.create_availability_control(
                "A1.1",
                "System Availability",
                "The system maintains availability at or above agreed-upon levels.",
                "infrastructure",
            ),
            self.create_availability_control(
                "A1.2",
                "Incident Response",
                "Incidents that impact availability are identified, classified, and responded to in a timely manner.",
                "operations",
            ),
            
            // Processing Integrity Controls
            self.create_processing_integrity_control(
                "PI1.1",
                "Data Processing Accuracy",
                "Data processing is complete, valid, accurate, timely, and authorized.",
                "application",
            ),
            
            // Confidentiality Controls
            self.create_confidentiality_control(
                "C1.1",
                "Confidential Information Protection",
                "Confidential information is protected to meet the entity's confidentiality commitments and requirements.",
                "data",
            ),
        ];
        
        let mut controls = self.controls.write().await;
        for control in default_controls {
            controls.insert(control.control_id.clone(), control);
        }
        
        // Update statistics
        {
            let mut stats = self.compliance_stats.write().await;
            stats.total_controls = controls.len() as u64;
            stats.implemented_controls = controls.values()
                .filter(|c| c.status == ControlStatus::Implemented)
                .count() as u64;
        }
        
        tracing::info!("Initialized {} SOC 2 controls", controls.len());
        Ok(())
    }

    /// Create security control
    fn create_security_control(&self, control_id: &str, name: &str, description: &str, owner: &str) -> SOC2Control {
        SOC2Control {
            control_id: control_id.to_string(),
            control_name: name.to_string(),
            control_type: SOC2ControlType::Security,
            description: description.to_string(),
            status: ControlStatus::NotImplemented,
            evidence: Vec::new(),
            last_assessment: None,
            next_assessment: Some(chrono::Utc::now() + chrono::Duration::days(90)),
            owner: owner.to_string(),
            maturity_level: 1,
        }
    }

    /// Create availability control
    fn create_availability_control(&self, control_id: &str, name: &str, description: &str, owner: &str) -> SOC2Control {
        SOC2Control {
            control_id: control_id.to_string(),
            control_name: name.to_string(),
            control_type: SOC2ControlType::Availability,
            description: description.to_string(),
            status: ControlStatus::NotImplemented,
            evidence: Vec::new(),
            last_assessment: None,
            next_assessment: Some(chrono::Utc::now() + chrono::Duration::days(90)),
            owner: owner.to_string(),
            maturity_level: 1,
        }
    }

    /// Create processing integrity control
    fn create_processing_integrity_control(&self, control_id: &str, name: &str, description: &str, owner: &str) -> SOC2Control {
        SOC2Control {
            control_id: control_id.to_string(),
            control_name: name.to_string(),
            control_type: SOC2ControlType::ProcessingIntegrity,
            description: description.to_string(),
            status: ControlStatus::NotImplemented,
            evidence: Vec::new(),
            last_assessment: None,
            next_assessment: Some(chrono::Utc::now() + chrono::Duration::days(90)),
            owner: owner.to_string(),
            maturity_level: 1,
        }
    }

    /// Create confidentiality control
    fn create_confidentiality_control(&self, control_id: &str, name: &str, description: &str, owner: &str) -> SOC2Control {
        SOC2Control {
            control_id: control_id.to_string(),
            control_name: name.to_string(),
            control_type: SOC2ControlType::Confidentiality,
            description: description.to_string(),
            status: ControlStatus::NotImplemented,
            evidence: Vec::new(),
            last_assessment: None,
            next_assessment: Some(chrono::Utc::now() + chrono::Duration::days(90)),
            owner: owner.to_string(),
            maturity_level: 1,
        }
    }

    /// Get all controls
    pub async fn get_controls(&self) -> Vec<SOC2Control> {
        let controls = self.controls.read().await;
        controls.values().cloned().collect()
    }

    /// Get control by ID
    pub async fn get_control(&self, control_id: &str) -> Option<SOC2Control> {
        let controls = self.controls.read().await;
        controls.get(control_id).cloned()
    }

    /// Update control status
    pub async fn update_control_status(&self, control_id: &str, status: ControlStatus, 
                                     maturity_level: u8) -> Result<()> {
        let mut controls = self.controls.write().await;
        
        if let Some(control) = controls.get_mut(control_id) {
            control.status = status.clone();
            control.maturity_level = maturity_level;
            control.last_assessment = Some(chrono::Utc::now());
            
            // Schedule next assessment based on status
            control.next_assessment = match status {
                ControlStatus::Implemented => Some(chrono::Utc::now() + chrono::Duration::days(180)),
                ControlStatus::PartiallyImplemented => Some(chrono::Utc::now() + chrono::Duration::days(90)),
                _ => Some(chrono::Utc::now() + chrono::Duration::days(30)),
            };
            
            // Log the update
            self.log_audit_event(
                "control_status_update",
                "compliance_manager",
                AuditOutcome::Success,
                vec![("control_id", control_id), ("new_status", &format!("{:?}", status))]
            ).await;
            
            // Update statistics
            self.update_compliance_stats().await;
            
            Ok(())
        } else {
            Err(CodeRabbitError::NotFound(format!("Control {} not found", control_id)))
        }
    }

    /// Add evidence to control
    pub async fn add_control_evidence(&self, control_id: &str, evidence: ControlEvidence) -> Result<()> {
        let mut controls = self.controls.write().await;
        
        if let Some(control) = controls.get_mut(control_id) {
            control.evidence.push(evidence.clone());
            
            // Store evidence separately for lookup
            let mut evidence_store = self.evidence_store.write().await;
            evidence_store.insert(evidence.evidence_id.clone(), evidence.clone());
            
            // Log the addition
            self.log_audit_event(
                "evidence_added",
                "compliance_manager", 
                AuditOutcome::Success,
                vec![("control_id", control_id), ("evidence_id", &evidence.evidence_id)]
            ).await;
            
            Ok(())
        } else {
            Err(CodeRabbitError::NotFound(format!("Control {} not found", control_id)))
        }
    }

    /// Collect automated evidence for controls
    pub async fn collect_automated_evidence(&self, control_id: &str) -> Result<ControlEvidence> {
        tracing::info!("Collecting automated evidence for control: {}", control_id);
        
        // Simulate evidence collection based on control type
        let evidence = match self.get_control(control_id).await {
            Some(control) => {
                match control.control_type {
                    SOC2ControlType::Security => self.collect_security_evidence(control_id).await,
                    SOC2ControlType::Availability => self.collect_availability_evidence(control_id).await,
                    SOC2ControlType::ProcessingIntegrity => self.collect_processing_integrity_evidence(control_id).await,
                    SOC2ControlType::Confidentiality => self.collect_confidentiality_evidence(control_id).await,
                    SOC2ControlType::Privacy => self.collect_privacy_evidence(control_id).await,
                }
            }
            None => return Err(CodeRabbitError::NotFound(format!("Control {} not found", control_id))),
        };
        
        // Add to control
        self.add_control_evidence(control_id, evidence.clone()).await?;
        
        Ok(evidence)
    }

    /// Collect security evidence
    async fn collect_security_evidence(&self, control_id: &str) -> ControlEvidence {
        // Simulate security evidence collection
        let security_check = match control_id {
            "CC6.1" => self.check_logical_access_security().await,
            "CC6.2" => self.check_user_access_provisioning().await,
            "CC6.6" => self.check_logical_access_controls().await,
            _ => 0.85,
        };
        
        ControlEvidence {
            evidence_id: format!("evidence_{}_{}", control_id, chrono::Utc::now().timestamp()),
            evidence_type: EvidenceType::MonitoringDashboard,
            description: format!("Automated security evidence collection for {}", control_id),
            file_path: None,
            timestamp: chrono::Utc::now(),
            collected_by: "compliance_system".to_string(),
            automated: true,
            validity_score: security_check,
        }
    }

    /// Collect availability evidence
    async fn collect_availability_evidence(&self, control_id: &str) -> ControlEvidence {
        let availability_score = match control_id {
            "A1.1" => self.check_system_availability().await,
            "A1.2" => self.check_incident_response().await,
            _ => 0.90,
        };
        
        ControlEvidence {
            evidence_id: format!("evidence_{}_{}", control_id, chrono::Utc::now().timestamp()),
            evidence_type: EvidenceType::MonitoringDashboard,
            description: format!("Automated availability evidence collection for {}", control_id),
            file_path: None,
            timestamp: chrono::Utc::now(),
            collected_by: "compliance_system".to_string(),
            automated: true,
            validity_score: availability_score,
        }
    }

    /// Collect processing integrity evidence
    async fn collect_processing_integrity_evidence(&self, control_id: &str) -> ControlEvidence {
        let integrity_score = self.check_data_processing_integrity().await;
        
        ControlEvidence {
            evidence_id: format!("evidence_{}_{}", control_id, chrono::Utc::now().timestamp()),
            evidence_type: EvidenceType::AuditLog,
            description: format!("Automated processing integrity evidence collection for {}", control_id),
            file_path: None,
            timestamp: chrono::Utc::now(),
            collected_by: "compliance_system".to_string(),
            automated: true,
            validity_score: integrity_score,
        }
    }

    /// Collect confidentiality evidence
    async fn collect_confidentiality_evidence(&self, control_id: &str) -> ControlEvidence {
        let confidentiality_score = self.check_confidential_information_protection().await;
        
        ControlEvidence {
            evidence_id: format!("evidence_{}_{}", control_id, chrono::Utc::now().timestamp()),
            evidence_type: EvidenceType::ConfigurationSnapshot,
            description: format!("Automated confidentiality evidence collection for {}", control_id),
            file_path: None,
            timestamp: chrono::Utc::now(),
            collected_by: "compliance_system".to_string(),
            automated: true,
            validity_score: confidentiality_score,
        }
    }

    /// Collect privacy evidence
    async fn collect_privacy_evidence(&self, control_id: &str) -> ControlEvidence {
        let privacy_score = self.check_privacy_controls().await;
        
        ControlEvidence {
            evidence_id: format!("evidence_{}_{}", control_id, chrono::Utc::now().timestamp()),
            evidence_type: EvidenceType::PolicyDocument,
            description: format!("Automated privacy evidence collection for {}", control_id),
            file_path: None,
            timestamp: chrono::Utc::now(),
            collected_by: "compliance_system".to_string(),
            automated: true,
            validity_score: privacy_score,
        }
    }

    /// Check logical access security
    async fn check_logical_access_security(&self) -> f32 {
        // Simulate checking logical access security
        // In a real implementation, this would check actual system configurations
        0.92 // 92% compliance score
    }

    /// Check user access provisioning
    async fn check_user_access_provisioning(&self) -> f32 {
        // Simulate checking user access provisioning process
        0.88
    }

    /// Check logical access controls
    async fn check_logical_access_controls(&self) -> f32 {
        // Simulate checking logical access controls
        0.95
    }

    /// Check system availability
    async fn check_system_availability(&self) -> f32 {
        // Simulate checking system availability metrics
        0.99
    }

    /// Check incident response
    async fn check_incident_response(&self) -> f32 {
        // Simulate checking incident response procedures
        0.85
    }

    /// Check data processing integrity
    async fn check_data_processing_integrity(&self) -> f32 {
        // Simulate checking data processing integrity
        0.91
    }

    /// Check confidential information protection
    async fn check_confidential_information_protection(&self) -> f32 {
        // Simulate checking confidential information protection
        0.87
    }

    /// Check privacy controls
    async fn check_privacy_controls(&self) -> f32 {
        // Simulate checking privacy controls
        0.83
    }

    /// Log audit event
    async fn log_audit_event(&self, action: &str, resource: &str, outcome: AuditOutcome, 
                           details: Vec<(&str, &str)>) {
        let mut audit_logs = self.audit_logs.write().await;
        
        let details_map: HashMap<String, String> = details.into_iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        
        let log_entry = AuditLogEntry {
            entry_id: format!("audit_{}", chrono::Utc::now().timestamp()),
            timestamp: chrono::Utc::now(),
            user_id: "system".to_string(),
            action: action.to_string(),
            resource: resource.to_string(),
            outcome,
            ip_address: None,
            user_agent: None,
            details: details_map,
        };
        
        audit_logs.push(log_entry);
        
        // Keep only recent logs (last 10000 entries)
        if audit_logs.len() > 10000 {
            let len = audit_logs.len(); audit_logs.drain(0..len - 10000);
        }
    }

    /// Update compliance statistics
    async fn update_compliance_stats(&self) {
        let controls = self.controls.read().await;
        let mut stats = self.compliance_stats.write().await;
        
        stats.total_controls = controls.len() as u64;
        stats.implemented_controls = controls.values()
            .filter(|c| c.status == ControlStatus::Implemented)
            .count() as u64;
        
        // Calculate compliance score
        if stats.total_controls > 0 {
            stats.compliance_score = (stats.implemented_controls as f32 / stats.total_controls as f32) * 100.0;
        }
        
        // Calculate automated controls percentage
        let automated_controls = controls.values()
            .filter(|c| c.evidence.iter().any(|e| e.automated))
            .count();
        
        if stats.total_controls > 0 {
            stats.automated_controls_percentage = (automated_controls as f32 / stats.total_controls as f32) * 100.0;
        }
        
        tracing::info!("Updated compliance stats: {:.1}% compliant", stats.compliance_score);
    }

    /// Get compliance statistics
    pub async fn get_compliance_stats(&self) -> ComplianceStats {
        let stats = self.compliance_stats.read().await;
        stats.clone()
    }

    /// Get audit logs
    pub async fn get_audit_logs(&self, limit: Option<usize>) -> Vec<AuditLogEntry> {
        let logs = self.audit_logs.read().await;
        let logs = logs.iter().rev().take(limit.unwrap_or(1000)).cloned().collect();
        logs
    }

    /// Run compliance assessment
    pub async fn run_compliance_assessment(&self) -> Result<ComplianceAssessment> {
        tracing::info!("Running comprehensive compliance assessment");
        
        let controls = self.get_controls().await;
        let mut assessment = ComplianceAssessment {
            assessment_id: format!("assessment_{}", chrono::Utc::now().timestamp()),
            timestamp: chrono::Utc::now(),
            overall_score: 0.0,
            control_scores: HashMap::new(),
            findings: Vec::new(),
            recommendations: Vec::new(),
            next_assessment_date: chrono::Utc::now() + chrono::Duration::days(90),
        };
        
        let mut total_score = 0.0;
        let mut control_count = 0;
        
        for control in controls {
            let control_score = self.assess_control(&control).await;
            assessment.control_scores.insert(control.control_id.clone(), control_score);
            
            if control_score < 80.0 {
                assessment.findings.push(ComplianceFinding {
                    finding_id: format!("finding_{}", chrono::Utc::now().timestamp()),
                    control_id: control.control_id.clone(),
                    severity: if control_score < 60.0 { "High".to_string() } else { "Medium".to_string() },
                    description: format!("Control {} has low compliance score: {:.1}%", 
                                      control.control_id, control_score),
                    recommendation: format!("Improve implementation of {} to achieve higher compliance", 
                                         control.control_name),
                });
            }
            
            total_score += control_score;
            control_count += 1;
        }
        
        if control_count > 0 {
            assessment.overall_score = total_score / control_count as f32;
        }
        
        // Generate recommendations
        assessment.recommendations = self.generate_recommendations(&assessment).await;
        
        // Log assessment completion
        self.log_audit_event(
            "compliance_assessment_completed",
            "compliance_manager",
            AuditOutcome::Success,
            vec![("overall_score", &format!("{:.1}", assessment.overall_score))]
        ).await;
        
        Ok(assessment)
    }

    /// Assess individual control
    async fn assess_control(&self, control: &SOC2Control) -> f32 {
        let mut score = 0.0;
        
        // Base score on implementation status
        score += match control.status {
            ControlStatus::Implemented => 60.0,
            ControlStatus::PartiallyImplemented => 30.0,
            ControlStatus::UnderReview => 45.0,
            ControlStatus::NotImplemented => 0.0,
            ControlStatus::NonCompliant => 10.0,
        };
        
        // Add points for maturity level
        score += (control.maturity_level as f32 / 5.0) * 25.0;
        
        // Add points for evidence quality
        if !control.evidence.is_empty() {
            let avg_evidence_quality = control.evidence.iter()
                .map(|e| e.validity_score)
                .sum::<f32>() / control.evidence.len() as f32;
            score += avg_evidence_quality * 15.0;
        }
        
        score.min(100.0)
    }

    /// Generate recommendations based on assessment
    async fn generate_recommendations(&self, assessment: &ComplianceAssessment) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        if assessment.overall_score < 80.0 {
            recommendations.push("Overall compliance score is below target. Focus on implementing missing controls.".to_string());
        }
        
        for (control_id, score) in &assessment.control_scores {
            if *score < 60.0 {
                recommendations.push(format!("Control {} requires immediate attention with score of {:.1}%", control_id, score));
            }
        }
        
        // Automated evidence recommendations
        let controls = self.get_controls().await;
        let low_automation_controls: Vec<_> = controls.iter()
            .filter(|c| c.evidence.iter().filter(|e| e.automated).count() < c.evidence.len() / 2)
            .collect();
        
        if !low_automation_controls.is_empty() {
            recommendations.push("Increase automation of evidence collection to improve efficiency and consistency.".to_string());
        }
        
        recommendations
    }

    /// Get evidence by ID
    pub async fn get_evidence(&self, evidence_id: &str) -> Option<ControlEvidence> {
        let evidence_store = self.evidence_store.read().await;
        evidence_store.get(evidence_id).cloned()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceAssessment {
    pub assessment_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub overall_score: f32,
    pub control_scores: HashMap<String, f32>,
    pub findings: Vec<ComplianceFinding>,
    pub recommendations: Vec<String>,
    pub next_assessment_date: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceFinding {
    pub finding_id: String,
    pub control_id: String,
    pub severity: String,
    pub description: String,
    pub recommendation: String,
}
