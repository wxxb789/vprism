---
description: Initialize a new specification with detailed project description and requirements
allowed-tools: Bash, Read, Write, Glob
---

# Spec Initialization

Initialize a new specification based on the provided project description:

**Project Description**: $ARGUMENTS

## Steering Context Validation

### Check Steering Documents
- Structure context: @.kiro/steering/structure.md
- Technical constraints: @.kiro/steering/tech.md  
- Product context: @.kiro/steering/product.md

### Verify Steering Exists
- Steering files: !`ls -la .kiro/steering/`

**FLEXIBILITY**: For new features or empty projects, steering documents are recommended but not required. If steering documents are missing or empty, you may proceed directly to spec generation phase.

## Task: Initialize Specification Structure

**SCOPE**: This command initializes the directory structure and metadata based on the detailed project description provided.

### 1. Analyze Project Description
From the provided description ($ARGUMENTS), extract:
- Project purpose and goals
- Key features and functionality
- Target users or use cases
- Technical requirements or constraints
- Any specific implementation details mentioned

### 2. Generate Feature Name
Based on the analysis, create a concise, descriptive feature name that captures the essence of the project.

### 3. Create Spec Directory
Create `.kiro/specs/{generated-feature-name}/` directory with template files:
- `requirements.md` - Empty template for user stories
- `design.md` - Empty template for technical design  
- `tasks.md` - Empty template for implementation tasks
- `spec.json` - Metadata and approval tracking

### 4. Initialize spec.json Metadata
Create initial metadata with approval tracking and project description:
```json
{
  "feature_name": "{generated-feature-name}",
  "project_description": "$ARGUMENTS",
  "created_at": "current_timestamp",
  "updated_at": "current_timestamp",
  "language": "Chinese",
  "phase": "initialized",
  "approvals": {
    "requirements": {
      "generated": false,
      "approved": false
    },
    "design": {
      "generated": false,
      "approved": false
    },
    "tasks": {
      "generated": false,
      "approved": false
    }
  },
  "progress": {
    "requirements": 0,
    "design": 0,
    "tasks": 0
  },
  "ready_for_implementation": false
}
```

### 5. Create Template Files with Project Context

#### requirements.md (Template with Context)
```markdown
# Requirements Document

## Project Overview
{Brief summary of the project based on the provided description}

## Project Description (User Input)
$ARGUMENTS

## Requirements
<!-- Detailed user stories will be generated in /spec-requirements phase -->

---
**STATUS**: Ready for requirements generation
**NEXT STEP**: Run `/spec-requirements {feature-name}` to generate detailed requirements
```

#### design.md (Empty Template)
```markdown
# Design Document

## Overview
<!-- Technical design will be generated after requirements approval -->

---
**STATUS**: Waiting for requirements approval
**NEXT STEP**: Complete and approve requirements first
```

#### tasks.md (Empty Template)
```markdown
# Implementation Plan

<!-- Implementation tasks will be generated after design approval -->

---
**STATUS**: Waiting for design approval  
**NEXT STEP**: Complete and approve design first
```

### 6. Update CLAUDE.md Reference
Add the new spec to the active specifications list with the generated feature name and a brief description.

## Next Steps After Initialization

Follow the proper spec-driven development workflow:

**Standard workflow:**
1. **Generate requirements**: `/spec-requirements {feature-name}`
2. **Review and approve requirements**: Update spec.json
3. **Generate design**: `/spec-design {feature-name}` (after requirements approval)
4. **Review and approve design**: Update spec.json
5. **Generate tasks**: `/spec-tasks {feature-name}` (after design approval)
6. **Review and approve tasks**: Update spec.json
7. **Start implementation**: After all approvals are complete

## Instructions

1. **Parse project description** - Extract key information from the detailed description
2. **Generate appropriate feature name** - Create a concise, descriptive name
3. **Check steering documents** - recommended but not required for new features
4. **Create directory structure** - Include project context in templates
5. **Set up approval tracking** in metadata with project description
6. **Provide clear next steps** for the user with the generated feature name
7. **Enable flexible workflow** - allow direct progression to requirements when appropriate

## Output Format

After initialization, provide:
1. Generated feature name and rationale
2. Brief project summary
3. Created file paths
4. Clear next steps with the exact command to run

This ensures the proper spec-driven development workflow with mandatory review phases between each step.