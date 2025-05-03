from typing import Any, Union, List
from enum import Enum
from pydantic import BaseModel

class SearchOperator(str, Enum):
    """Search operators supported by the API."""
    EQUALS = ":"
    NOT_EQUALS = "!:"
    CONTAINS = "~"
    NOT_CONTAINS = "!~"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN_OR_EQUAL = "<="

class SearchCondition(BaseModel):
    """A single search condition."""
    field: str
    operator: SearchOperator
    value: Any

    def __str__(self) -> str:
        """Convert the condition to search language syntax."""
        return f'{self.field}{self.operator.value}"{self.value}"'

class SearchQuery:
    """Builder for search queries."""
    
    def __init__(self) -> None:
        self.conditions: List[SearchCondition] = []
        self.operators: List[str] = []
    
    def add_condition(
        self,
        field: str,
        operator: SearchOperator,
        value: Any,
        combine_with: str = "AND"
    ) -> "SearchQuery":
        """Add a search condition.
        
        Args:
            field: The field to search in
            operator: The search operator to use
            value: The value to search for
            combine_with: How to combine with previous condition ("AND" or "OR")
            
        Returns:
            The SearchQuery instance for method chaining
        """
        if self.conditions:
            self.operators.append(combine_with)
        self.conditions.append(SearchCondition(
            field=field,
            operator=operator,
            value=value
        ))
        return self
    
    def equals(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add an equals condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.EQUALS, value, combine_with)
    
    def not_equals(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a not equals condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.NOT_EQUALS, value, combine_with)
    
    def contains(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a contains condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.CONTAINS, value, combine_with)
    
    def not_contains(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a not contains condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.NOT_CONTAINS, value, combine_with)
    
    def greater_than(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a greater than condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.GREATER_THAN, value, combine_with)
    
    def less_than(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a less than condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.LESS_THAN, value, combine_with)
    
    def greater_than_or_equal(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a greater than or equal condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.GREATER_THAN_OR_EQUAL, value, combine_with)
    
    def less_than_or_equal(self, field: str, value: Any, combine_with: str = "AND") -> "SearchQuery":
        """Add a less than or equal condition.
        
        Args:
            field: The field to search in
            value: The value to search for
            combine_with: How to combine with previous condition
            
        Returns:
            The SearchQuery instance for method chaining
        """
        return self.add_condition(field, SearchOperator.LESS_THAN_OR_EQUAL, value, combine_with)
    
    def build(self) -> str:
        """Build the search query string.
        
        Returns:
            The search query string
        """
        if not self.conditions:
            return ""
            
        parts = [str(self.conditions[0])]
        for op, cond in zip(self.operators, self.conditions[1:]):
            parts.append(op)
            parts.append(str(cond))
            
        return " ".join(parts) 