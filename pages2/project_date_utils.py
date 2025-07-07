import streamlit as st
from datetime import date, timedelta
from typing import Dict, List, Optional, Union, Tuple

class ProjectDateValidator:
    """Unified date validator for projects, stages, and substages"""
    
    def __init__(self, stage_assignments: Dict, project_due_date: Union[date, str]):
        self.stage_assignments = stage_assignments or {}
        self.project_due_date = self._parse_date(project_due_date)
        self.errors = []
        self.conflicts = {
            "stage_vs_project": [],
            "substage_vs_project": [],
            "substage_vs_stage": [],
            "invalid_formats": []
        }
    
    def _parse_date(self, date_input: Union[date, str, None]) -> Optional[date]:
        """Safely parse date from string or date object"""
        if not date_input:
            return None
        
        if isinstance(date_input, date):
            return date_input
        
        if isinstance(date_input, str):
            try:
                return date.fromisoformat(date_input)
            except (ValueError, TypeError):
                return None
        
        return None
    
    def _validate_single_deadline(self, deadline: Union[date, str, None], 
                                 reference_date: Optional[date], 
                                 deadline_name: str, 
                                 reference_name: str) -> Tuple[Optional[date], bool]:
        """
        Validate a single deadline against a reference date
        Returns (parsed_date, is_valid)
        """
        if not deadline:
            return None, True
        
        parsed_deadline = self._parse_date(deadline)
        
        if parsed_deadline is None:
            self.conflicts["invalid_formats"].append({
                "name": deadline_name,
                "deadline": str(deadline),
                "type": "invalid_format"
            })
            return None, False
        
        if reference_date and parsed_deadline > reference_date:
            return parsed_deadline, False
        
        return parsed_deadline, True
    
    def validate_stage_deadline(self, stage_key: str, stage_data: Dict, stage_name: str) -> Optional[date]:
        """Validate stage deadline against project due date"""
        stage_deadline = stage_data.get("deadline")
        
        if not stage_deadline:
            return None
        
        parsed_deadline, is_valid = self._validate_single_deadline(
            stage_deadline, self.project_due_date, f"Stage '{stage_name}'", "project"
        )
        
        if not is_valid and parsed_deadline:
            self.conflicts["stage_vs_project"].append({
                "stage_name": stage_name,
                "stage_deadline": parsed_deadline.isoformat(),
                "project_due": self.project_due_date.isoformat() if self.project_due_date else "N/A"
            })
            self.errors.append(
                f"Stage '{stage_name}' deadline ({parsed_deadline}) cannot be after project due date ({self.project_due_date})"
            )
        
        return parsed_deadline
    
    def validate_substage_deadlines(self, stage_key: str, stage_data: Dict, 
                                   stage_name: str, stage_deadline: Optional[date]) -> None:
        """Validate all substage deadlines for a stage"""
        substages = stage_data.get("substages", [])
        
        for idx, substage in enumerate(substages):
            substage_deadline = substage.get("deadline")
            substage_name = substage.get("name", f"Substage {idx + 1}")
            
            if not substage_deadline:
                continue
            
            parsed_deadline, is_valid_vs_project = self._validate_single_deadline(
                substage_deadline, self.project_due_date, 
                f"Substage '{substage_name}' in stage '{stage_name}'", "project"
            )
            
            if parsed_deadline is None:
                continue
            
            # Check against project due date
            if not is_valid_vs_project:
                self.conflicts["substage_vs_project"].append({
                    "stage_name": stage_name,
                    "substage_name": substage_name,
                    "substage_deadline": parsed_deadline.isoformat(),
                    "project_due": self.project_due_date.isoformat() if self.project_due_date else "N/A"
                })
                self.errors.append(
                    f"Substage '{substage_name}' in stage '{stage_name}' deadline ({parsed_deadline}) cannot be after project due date ({self.project_due_date})"
                )
            
            # Check against stage deadline
            if stage_deadline and parsed_deadline > stage_deadline:
                self.conflicts["substage_vs_stage"].append({
                    "stage_name": stage_name,
                    "substage_name": substage_name,
                    "substage_deadline": parsed_deadline.isoformat(),
                    "stage_deadline": stage_deadline.isoformat()
                })
                self.errors.append(
                    f"Substage '{substage_name}' deadline ({parsed_deadline}) cannot be after its parent stage '{stage_name}' deadline ({stage_deadline})"
                )
    
    def validate_all_dates(self) -> Dict:
        """
        Perform comprehensive date validation
        Returns validation results with errors and conflicts
        """
        if not self.stage_assignments or not self.project_due_date:
            return self.get_validation_results()
        
        for stage_key, stage_data in self.stage_assignments.items():
            if not isinstance(stage_data, dict):
                continue
            
            stage_name = stage_data.get("stage_name", f"Stage {stage_key}")
            
            # Validate stage deadline
            stage_deadline = self.validate_stage_deadline(stage_key, stage_data, stage_name)
            
            # Validate substage deadlines
            self.validate_substage_deadlines(stage_key, stage_data, stage_name, stage_deadline)
        
        return self.get_validation_results()
    
    def get_validation_results(self) -> Dict:
        """Get comprehensive validation results"""
        return {
            "is_valid": len(self.errors) == 0,
            "errors": self.errors,
            "conflicts": self.conflicts,
            "error_count": len(self.errors),
            "conflict_summary": self._get_conflict_summary()
        }
    
    def _get_conflict_summary(self) -> Dict:
        """Get summary of conflicts by type"""
        return {
            "stage_vs_project": len(self.conflicts["stage_vs_project"]),
            "substage_vs_project": len(self.conflicts["substage_vs_project"]),
            "substage_vs_stage": len(self.conflicts["substage_vs_stage"]),
            "invalid_formats": len(self.conflicts["invalid_formats"]),
            "total_conflicts": sum(len(conflicts) for conflicts in self.conflicts.values())
        }
    
    def display_validation_errors(self) -> None:
        """Display validation errors in Streamlit UI"""
        if not self.errors:
            return
        
        st.error("⚠️ **Deadline Conflicts Detected:**")
        
        if self.conflicts["stage_vs_project"]:
            st.error("**Stages with deadlines after project due date:**")
            for conflict in self.conflicts["stage_vs_project"]:
                st.error(f"  • {conflict['stage_name']}: {conflict['stage_deadline']} (Project due: {conflict['project_due']})")
        
        if self.conflicts["substage_vs_project"]:
            st.error("**Substages with deadlines after project due date:**")
            for conflict in self.conflicts["substage_vs_project"]:
                st.error(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']} (Project due: {conflict['project_due']})")
        
        if self.conflicts["substage_vs_stage"]:
            st.error("**Substages with deadlines after their stage deadline:**")
            for conflict in self.conflicts["substage_vs_stage"]:
                st.error(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']} (Stage due: {conflict['stage_deadline']})")
        
        if self.conflicts["invalid_formats"]:
            st.error("**Invalid deadline formats:**")
            for conflict in self.conflicts["invalid_formats"]:
                st.error(f"  • {conflict['name']}: {conflict['deadline']}")
    
    def get_detailed_conflict_report(self) -> str:
        """Get a detailed text report of all conflicts"""
        if not self.errors:
            return "✅ No date conflicts found."
        
        report = ["📋 **Date Validation Report**", ""]
        
        if self.conflicts["stage_vs_project"]:
            report.append("🔴 **Stages exceeding project deadline:**")
            for conflict in self.conflicts["stage_vs_project"]:
                report.append(f"  • {conflict['stage_name']}: {conflict['stage_deadline']}")
            report.append("")
        
        if self.conflicts["substage_vs_project"]:
            report.append("🔴 **Substages exceeding project deadline:**")
            for conflict in self.conflicts["substage_vs_project"]:
                report.append(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']}")
            report.append("")
        
        if self.conflicts["substage_vs_stage"]:
            report.append("🔴 **Substages exceeding stage deadline:**")
            for conflict in self.conflicts["substage_vs_stage"]:
                report.append(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']}")
            report.append("")
        
        if self.conflicts["invalid_formats"]:
            report.append("🔴 **Invalid date formats:**")
            for conflict in self.conflicts["invalid_formats"]:
                report.append(f"  • {conflict['name']}: {conflict['deadline']}")
        
        return "\n".join(report)


def auto_adjust_stage_dates(stage_assignments, old_due_date, new_due_date):
    """
    Automatically adjust stage and substage dates when project due date changes
    Proportionally scales dates to fit within new timeline
    """
    if not stage_assignments or old_due_date == new_due_date:
        return stage_assignments
    
    # Calculate the scaling factor
    old_duration = (old_due_date - date.today()).days
    new_duration = (new_due_date - date.today()).days
    
    if old_duration <= 0:
        return stage_assignments  # Can't scale if old duration is invalid
    
    scale_factor = new_duration / old_duration
    
    adjusted_assignments = {}
    
    for stage_key, stage_data in stage_assignments.items():
        adjusted_stage = stage_data.copy()
        
        # Adjust main stage deadline
        if "deadline" in stage_data and stage_data["deadline"]:
            try:
                stage_deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                days_from_today = (stage_deadline - date.today()).days
                new_days = int(days_from_today * scale_factor)
                new_deadline = date.today() + timedelta(days=max(1, new_days))
                
                # Ensure it doesn't exceed project due date
                if new_deadline > new_due_date:
                    new_deadline = new_due_date
                
                adjusted_stage["deadline"] = new_deadline.isoformat()
            except (ValueError, TypeError):
                pass  # Keep original if conversion fails
        
        # Adjust substage deadlines
        if "substages" in stage_data:
            adjusted_substages = []
            for substage in stage_data["substages"]:
                adjusted_substage = substage.copy()
                
                if "deadline" in substage and substage["deadline"]:
                    try:
                        substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                        days_from_today = (substage_deadline - date.today()).days
                        new_days = int(days_from_today * scale_factor)
                        new_deadline = date.today() + timedelta(days=max(1, new_days))
                        
                        # Ensure it doesn't exceed project due date
                        if new_deadline > new_due_date:
                            new_deadline = new_due_date
                        
                        adjusted_substage["deadline"] = new_deadline.isoformat()
                    except (ValueError, TypeError):
                        pass  # Keep original if conversion fails
                
                adjusted_substages.append(adjusted_substage)
            
            adjusted_stage["substages"] = adjusted_substages
        
        adjusted_assignments[stage_key] = adjusted_stage
    
    return adjusted_assignments


def auto_adjust_substage_dates_to_stage(stage_deadline, substages):
    """
    Automatically adjust substage dates when stage deadline changes
    Ensures all substage deadlines are <= stage deadline
    """
    if not stage_deadline or not substages:
        return substages
    
    try:
        # Convert stage deadline to date object if it's a string
        if isinstance(stage_deadline, str):
            stage_deadline = date.fromisoformat(stage_deadline)
        
        adjusted_substages = []
        
        for substage in substages:
            adjusted_substage = substage.copy()
            
            if "deadline" in substage and substage["deadline"]:
                try:
                    substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                    
                    # If substage deadline is after stage deadline, adjust it
                    if substage_deadline > stage_deadline:
                        adjusted_substage["deadline"] = stage_deadline.isoformat()
                        # Optionally add a flag to indicate it was auto-adjusted
                        adjusted_substage["_auto_adjusted"] = True
                
                except (ValueError, TypeError):
                    # Keep original if conversion fails
                    pass
            
            adjusted_substages.append(adjusted_substage)
        
        return adjusted_substages
        
    except (ValueError, TypeError):
        return substages  # Return original if stage deadline conversion fails
    
# NEW FUNCTION: Check for overdue stages and substages
def get_overdue_stages_and_substages(stage_assignments, project_levels, current_level):
    
    """
    Get all overdue stages and substages
    Returns list of overdue items with details
    """
    overdue_items = []
    today = date.today()
    
    if not stage_assignments:
        return overdue_items
    
    for stage_idx in range(min(current_level + 2, len(project_levels))):  # Check current and next stage
        stage_key = str(stage_idx)
        
        if stage_key not in stage_assignments:
            continue
        
        stage_data = stage_assignments[stage_key]
        stage_name = stage_data.get("stage_name", project_levels[stage_idx] if stage_idx < len(project_levels) else f"Stage {stage_idx}")
        
        # Check main stage deadline (only if not completed)
        if stage_idx > current_level and "deadline" in stage_data and stage_data["deadline"]:
            try:
                deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                if deadline < today:
                    days_overdue = (today - deadline).days
                    overdue_items.append({
                        "type": "stage",
                        "stage_index": stage_idx,
                        "stage_name": stage_name,
                        "deadline": deadline.isoformat(),
                        "days_overdue": days_overdue
                    })
            except (ValueError, TypeError):
                pass
        
        # Check substage deadlines
        substages = stage_data.get("substages", [])
        for substage_idx, substage in enumerate(substages):
            if "deadline" in substage and substage["deadline"]:
                try:
                    deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                    if deadline < today:
                        days_overdue = (today - deadline).days
                        substage_name = substage.get("name", f"Substage {substage_idx + 1}")
                        overdue_items.append({
                            "type": "substage",
                            "stage_index": stage_idx,
                            "stage_name": stage_name,
                            "substage_index": substage_idx,
                            "substage_name": substage_name,
                            "deadline": deadline.isoformat(),
                            "days_overdue": days_overdue
                        })
                except (ValueError, TypeError):
                    pass
    
    return overdue_items


# Backward compatibility wrapper functions
def validate_stage_substage_dates(stage_assignments: Dict, project_due_date: Union[date, str], 
                                 display_conflicts: bool = True) -> List[str]:
    """
    Wrapper function for backward compatibility
    Validate that all stage and substage due dates are <= project due date
    """
    validator = ProjectDateValidator(stage_assignments, project_due_date)
    results = validator.validate_all_dates()
    
    if display_conflicts and not results["is_valid"]:
        validator.display_validation_errors()
    
    return results["errors"]

def validate_substage_deadline_against_stage(stage_deadline: Union[date, str], 
                                           substage_deadline: Union[date, str], 
                                           stage_name: str, 
                                           substage_name: str) -> Optional[str]:
    """
    Wrapper function for backward compatibility
    Validate a single substage deadline against its parent stage deadline
    """
    # Create a minimal stage assignment for validation
    stage_assignments = {
        "0": {
            "stage_name": stage_name,
            "deadline": stage_deadline,
            "substages": [{
                "name": substage_name,
                "deadline": substage_deadline
            }]
        }
    }
    
    validator = ProjectDateValidator(stage_assignments, "2099-12-31")  # Dummy project date
    results = validator.validate_all_dates()
    
    # Return the first substage vs stage error if any
    substage_vs_stage_errors = [
        error for error in results["errors"] 
        if substage_name in error and stage_name in error and "cannot be after its parent stage" in error
    ]
    
    return substage_vs_stage_errors[0] if substage_vs_stage_errors else None

def get_deadline_conflicts_summary(stage_assignments: Dict, project_due_date: Union[date, str]) -> Dict:
    """
    Wrapper function for backward compatibility
    Get a summary of all deadline conflicts
    """
    validator = ProjectDateValidator(stage_assignments, project_due_date)
    results = validator.validate_all_dates()
    return results["conflicts"]


def display_deadline_conflicts(conflicts: Dict) -> None:
    """
    Wrapper function for backward compatibility
    Display deadline conflicts in Streamlit UI
    """
    # Create a validator just for display purposes
    validator = ProjectDateValidator({}, "2099-12-31")
    validator.conflicts = conflicts
    validator.errors = ["Conflicts detected"]  # Dummy error to trigger display
    validator.display_validation_errors()


# Enhanced validation function for comprehensive project validation
def validate_project_dates_comprehensive(stage_assignments: Dict, 
                                       project_due_date: Union[date, str],
                                       return_detailed_report: bool = False) -> Union[bool, Dict]:
    """
    Comprehensive project date validation with detailed reporting
    
    Args:
        stage_assignments: Dictionary of stage assignments
        project_due_date: Project due date
        return_detailed_report: If True, returns detailed validation results
        
    Returns:
        bool: True if valid (when return_detailed_report=False)
        Dict: Detailed validation results (when return_detailed_report=True)
    """
    validator = ProjectDateValidator(stage_assignments, project_due_date)
    results = validator.validate_all_dates()
    
    if return_detailed_report:
        results["detailed_report"] = validator.get_detailed_conflict_report()
        return results
    
    return results["is_valid"]