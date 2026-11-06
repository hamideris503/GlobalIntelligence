# ADR-004: Shared AI execution architecture
Context: Many modules need models.
Current State: AIGateway single entry point.
Problem: Provider hard-coding risk.
Decision: All AI through gateway; provider catalog + eligibility + free policy. No direct provider calls in domains.
Consequences: Centralized policy, token ledger, budget.
Migration: None.
Rollback: N/A.
Tests: AI integrity tests.
