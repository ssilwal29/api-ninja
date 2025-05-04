from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional, Annotated
from uuid import uuid4
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

# --------
# Models
# --------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str


class ContactInfo(BaseModel):
    email: EmailStr
    phone: Optional[str] = None


class User(BaseModel):
    id: str
    name: str
    age: int = Field(..., gt=0, lt=130)
    address: Address
    contact: ContactInfo
    tags: List[str] = []


class CreateUserRequest(BaseModel):
    name: str
    age: int
    address: Address
    contact: ContactInfo
    tags: List[str] = []


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = Field(None, gt=0, lt=130)
    address: Optional[Address] = None
    contact: Optional[ContactInfo] = None
    tags: Optional[List[str]] = None


class TagUpdateRequest(BaseModel):
    tags: List[str]


# --------
# Mock Store
# --------

mock_db: Dict[str, User] = {}

# --------
# CRUD Endpoints
# --------


@app.post("/users", response_model=User)
def create_user(user_req: CreateUserRequest):
    user_id = str(uuid4())
    new_user = User(id=user_id, **user_req.model_dump())
    mock_db[user_id] = new_user
    return new_user


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: str):
    user = mock_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users", response_model=List[User])
def list_users():
    return list(mock_db.values())


@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: str, user_req: UpdateUserRequest):
    existing_user = mock_db.get(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_data = user_req.dict(exclude_unset=True)
    updated_user = existing_user.copy(update=updated_data)
    mock_db[user_id] = updated_user
    return updated_user


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str):
    if user_id not in mock_db:
        raise HTTPException(status_code=404, detail="User not found")
    del mock_db[user_id]
    return Response(status_code=204)


# --------
# Extra Functional Endpoints
# --------


@app.get("/search", response_model=List[User])
def search_users(name: Optional[str] = Query(None), city: Optional[str] = Query(None)):
    results = list(mock_db.values())
    if name:
        results = [u for u in results if name.lower() in u.name.lower()]
    if city:
        results = [u for u in results if city.lower() in u.address.city.lower()]
    return results


@app.post("/batch", response_model=List[User])
def batch_create_users(users: List[CreateUserRequest]):
    new_users = []
    for user_req in users:
        user_id = str(uuid4())
        new_user = User(id=user_id, **user_req.dict())
        mock_db[user_id] = new_user
        new_users.append(new_user)
    return new_users


@app.patch("/users/{user_id}/deactivate", response_model=User)
def deactivate_user(user_id: str):
    user = mock_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_user = user.copy(update={"tags": user.tags + ["inactive"]})
    mock_db[user_id] = updated_user
    return updated_user


@app.post("/users/{user_id}/tags", response_model=User)
def add_tags_to_user(user_id: str, tags_req: TagUpdateRequest):
    user = mock_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_tags = list(set(user.tags + tags_req.tags))  # avoid duplicates
    updated_user = user.copy(update={"tags": updated_tags})
    mock_db[user_id] = updated_user
    return updated_user


@app.get("/stats")
def get_user_stats():
    total_users = len(mock_db)
    inactive_users = sum(1 for u in mock_db.values() if "inactive" in u.tags)
    tags_summary = {}
    for u in mock_db.values():
        for tag in u.tags:
            tags_summary[tag] = tags_summary.get(tag, 0) + 1
    return {
        "total_users": total_users,
        "inactive_users": inactive_users,
        "tags_summary": tags_summary,
    }


# --------
# Simulate Auth + Profile Route
# --------
@app.get("/items/")
async def read_items(user_agent: Annotated[str | None, Header()] = None):
    return {"User-Agent": user_agent}


def verify_token(x_token: Optional[str | None] = Header(None)):
    if x_token != "secrettoken":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/login/", dependencies=[Depends(verify_token)])
def get_protected_info():
    return {"message": "This is protected info"}


@app.post("/login/{user_id}/profile", response_model=User)
def get_user_profile(user_id: str):
    user = mock_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
