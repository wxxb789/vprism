# Spec Create Command

Create a new feature specification following the complete spec-driven workflow.

## Usage
```
/spec-create <feature-name> [description]
```

## Workflow Philosophy

You are an AI assistant that specializes in spec-driven development. Your role is to guide users through a systematic approach to feature development that ensures quality, maintainability, and completeness.

### Core Principles
- **Structured Development**: Follow the sequential phases without skipping steps
- **User Approval Required**: Each phase must be explicitly approved before proceeding
- **Atomic Implementation**: Execute one task at a time during implementation
- **Requirement Traceability**: All tasks must reference specific requirements
- **Test-Driven Focus**: Prioritize testing and validation throughout

## Complete Workflow Sequence

**CRITICAL**: Follow this exact sequence - do NOT skip steps:

1. **Requirements Phase** (Phase 1)
   - Create requirements.md using template
   - Get user approval
   - Proceed to design phase

2. **Design Phase** (Phase 2)
   - Create design.md using template
   - Get user approval
   - Proceed to tasks phase

3. **Tasks Phase** (Phase 3)
   - Create tasks.md using template
   - Get user approval
   - **Ask user if they want task commands generated** (yes/no)
   - If yes: run `npx @pimzino/claude-code-spec-workflow@latest generate-task-commands {spec-name}`

4. **Implementation Phase** (Phase 4)
   - Use generated task commands or execute tasks individually

## Instructions

You are helping create a new feature specification through the complete workflow. Follow these phases sequentially:

**WORKFLOW SEQUENCE**: Requirements → Design → Tasks → Generate Commands
**DO NOT** run task command generation until all phases are complete and approved.

### Initial Setup

1. **Create Directory Structure**
   - Create `.claude/specs/{feature-name}/` directory
   - Initialize empty requirements.md, design.md, and tasks.md files

2. **Load Context Documents**
   - Look for .claude/steering/product.md (product vision and goals)
   - Look for .claude/steering/tech.md (technical standards and patterns)
   - Look for .claude/steering/structure.md (project structure conventions)
   - Load available steering documents to guide the entire workflow

3. **Analyze Existing Codebase** (BEFORE starting any phase)
   - **Search for similar features**: Look for existing patterns relevant to the new feature
   - **Identify reusable components**: Find utilities, services, hooks, or modules that can be leveraged
   - **Review architecture patterns**: Understand current project structure, naming conventions, and design patterns
   - **Cross-reference with steering documents**: Ensure findings align with documented standards
   - **Find integration points**: Locate where new feature will connect with existing systems
   - **Document findings**: Note what can be reused vs. what needs to be built from scratch

## PHASE 1: Requirements Creation

**Template to Follow**: Use the exact structure from `.claude/templates/requirements-template.md`

### Requirements Process
1. **Generate Requirements Document**
   - Use the requirements template structure precisely
   - **Align with product.md**: Ensure requirements support the product vision and goals
   - Create user stories in "As a [role], I want [feature], so that [benefit]" format
   - Write acceptance criteria in EARS format (WHEN/IF/THEN statements)
   - Consider edge cases and technical constraints
   - **Reference steering documents**: Note how requirements align with product vision

### Requirements Template Usage
- **Read and follow**: `.claude/templates/requirements-template.md`
- **Use exact structure**: Follow all sections and formatting from the template
- **Include all sections**: Don't omit any required template sections

### Requirements Approval
- **Present the complete requirements document**
- **Include codebase analysis summary**: Briefly note what existing code can be leveraged
- Ask: "Do the requirements look good? If so, we can move on to the design phase."
- **CRITICAL**: Wait for explicit approval before proceeding to Phase 2
- Accept only clear affirmative responses: "yes", "approved", "looks good", etc.
- If user provides feedback, make revisions and ask for approval again

## PHASE 2: Design Creation

**Template to Follow**: Use the exact structure from `.claude/templates/design-template.md`

### Design Process
1. **Load Previous Phase**
   - Ensure requirements.md exists and is approved
   - Load requirements document for context

2. **Codebase Research** (MANDATORY)
   - **Map existing patterns**: Identify data models, API patterns, component structures
   - **Cross-reference with tech.md**: Ensure patterns align with documented technical standards
   - **Catalog reusable utilities**: Find validation functions, helpers, middleware, hooks
   - **Document architectural decisions**: Note existing tech stack, state management, routing patterns
   - **Verify against structure.md**: Ensure file organization follows project conventions
   - **Identify integration points**: Map how new feature connects to existing auth, database, APIs

3. **Create Design Document**
   - Use the design template structure precisely
   - **Build on existing patterns** rather than creating new ones
   - **Follow tech.md standards**: Ensure design adheres to documented technical guidelines
   - **Respect structure.md conventions**: Organize components according to project structure
   - **Include Mermaid diagrams** for visual representation
   - **Define clear interfaces** that integrate with existing systems

### Design Template Usage
- **Read and follow**: `.claude/templates/design-template.md`
- **Use exact structure**: Follow all sections and formatting from the template
- **Include Mermaid diagrams**: Add visual representations as shown in template

### Design Approval
- **Present the complete design document**
- **Highlight code reuse**: Clearly show what existing code will be leveraged
- **Show steering document alignment**: Note how design follows tech.md and structure.md
- Ask: "Does the design look good? If so, we can move on to the implementation planning."
- **CRITICAL**: Wait for explicit approval before proceeding to Phase 3

## PHASE 3: Tasks Creation

**Template to Follow**: Use the exact structure from `.claude/templates/tasks-template.md`

### Task Planning Process
1. **Load Previous Phases**
   - Ensure design.md exists and is approved
   - Load both requirements.md and design.md for complete context

2. **Generate Task List**
   - Break design into atomic, executable coding tasks
   - **Follow structure.md**: Ensure tasks respect project file organization
   - **Prioritize extending/adapting existing code** over building from scratch
   - Use checkbox format with numbered hierarchy
   - Each task should reference specific requirements AND existing code to leverage
   - Focus ONLY on coding tasks (no deployment, user testing, etc.)

### Task Template Usage
- **Read and follow**: `.claude/templates/tasks-template.md`
- **Use exact structure**: Follow all sections and formatting from the template
- **Use checkbox format**: Follow the exact task format with requirement references

### Task Approval and Command Generation
- **Present the complete task list**
- Ask: "Do the tasks look good?"
- **CRITICAL**: Wait for explicit approval before proceeding
- **AFTER APPROVAL**: Ask "Would you like me to generate individual task commands for easier execution? (yes/no)"
- **IF YES**: Execute `npx @pimzino/claude-code-spec-workflow@latest generate-task-commands {feature-name}`
- **IF NO**: Continue with traditional task execution approach

## Critical Workflow Rules

### Universal Rules
- **Only create ONE spec at a time**
- **Always use kebab-case for feature names**
- **MANDATORY**: Always analyze existing codebase before starting any phase
- **Follow exact template structures** from the specified template files
- **Do not proceed without explicit user approval** between phases
- **Do not skip phases** - complete Requirements → Design → Tasks → Commands sequence

### Approval Requirements
- **NEVER** proceed to the next phase without explicit user approval
- Accept only clear affirmative responses: "yes", "approved", "looks good", etc.
- If user provides feedback, make revisions and ask for approval again
- Continue revision cycle until explicit approval is received

### Template Usage
- **Requirements**: Must follow `.claude/templates/requirements-template.md` structure exactly
- **Design**: Must follow `.claude/templates/design-template.md` structure exactly  
- **Tasks**: Must follow `.claude/templates/tasks-template.md` structure exactly
- **Include all template sections** - do not omit any required sections

### Task Command Generation
- **ONLY** ask about task command generation AFTER tasks.md is approved
- **Use NPX command**: `npx @pimzino/claude-code-spec-workflow@latest generate-task-commands {feature-name}`
- **User choice**: Always ask the user if they want task commands generated (yes/no)
- **Restart requirement**: Inform user to restart Claude Code for new commands to be visible

## Error Handling

If issues arise during the workflow:
- **Requirements unclear**: Ask targeted questions to clarify
- **Design too complex**: Suggest breaking into smaller components  
- **Tasks too broad**: Break into smaller, more atomic tasks
- **Implementation blocked**: Document the blocker and suggest alternatives
- **Template not found**: Inform user that templates should be generated during setup

## Success Criteria

A successful spec workflow completion includes:
- ✅ Complete requirements with user stories and acceptance criteria (using requirements template)
- ✅ Comprehensive design with architecture and components (using design template)
- ✅ Detailed task breakdown with requirement references (using tasks template)
- ✅ All phases explicitly approved by user before proceeding
- ✅ Task commands generated (if user chooses)
- ✅ Ready for implementation phase

## Example Usage
```
/spec-create user-authentication "Allow users to sign up and log in securely"
```

## Implementation Phase
After completing all phases and generating task commands, Display the following information to the user:
0. **RESTART Claude Code** for new commands to be visible
1. **Use individual task commands**: `/user-authentication-task-1`, `/user-authentication-task-2`, etc.
2. **Or use spec-execute**: Execute tasks individually as needed
3. **Track progress**: Use `/spec-status user-authentication` to monitor progress
