# Реализация: GET /workspaces/{id}/users

Экран "Screen/Users List" из дизайна — список участников workspace с поиском и фильтрацией по роли.

---

## Backend

### Endpoint

```
GET /workspaces/{id}/users
```

**Доступ:** любой активный член workspace (`workspace_admin`, `assistant`, `client`) + `super_admin`.

**Query-параметры:**

| Параметр | Тип                                      | Описание                                       |
|----------|------------------------------------------|------------------------------------------------|
| `role`   | `workspace_admin` \| `assistant` \| `client` | Фильтр по роли (опционально)              |
| `search` | `string`                                 | Поиск по `full_name` и `username` (опционально)|

---

### Схема ответа

```python
# app/modules/workspaces/schemas.py

class WorkspaceUserResponse(BaseModel):
    id: UUID
    full_name: str
    username: str | None
    role: WorkspaceRole
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

### Service

```python
# app/modules/workspaces/service.py

async def list_users(
    self,
    workspace_id: UUID,
    role: WorkspaceRole | None,
    search: str | None,
) -> list[WorkspaceUserResponse]:
    query = (
        select(User, WorkspaceMember.role, WorkspaceMember.joined_at)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.is_active.is_(True),
        )
        .order_by(WorkspaceMember.joined_at.desc())
    )

    if role is not None:
        query = query.where(WorkspaceMember.role == role)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                User.full_name.ilike(pattern),
                User.username.ilike(pattern),
            )
        )

    result = await self.session.execute(query)
    return [
        WorkspaceUserResponse(
            id=user.id,
            full_name=user.full_name,
            username=user.username,
            role=member_role,
            joined_at=joined_at,
        )
        for user, member_role, joined_at in result.all()
    ]
```

---

### Router

```python
# app/modules/workspaces/router.py

@router.get(
    "/{id}/users",
    response_model=list[WorkspaceUserResponse],
    summary="List workspace users",
    description="Returns active members of a workspace with optional role and search filters.",
)
async def list_workspace_users(
    id: UUID,
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
    role: Annotated[WorkspaceRole | None, Query()] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> list[WorkspaceUserResponse]:
    del access
    return await service.list_users(id, role, search)
```

---

### Response 200

```json
[
  {
    "id": "uuid",
    "full_name": "Алексей Иванов",
    "username": "alexei_i",
    "role": "workspace_admin",
    "joined_at": "2026-01-15T10:00:00Z"
  },
  {
    "id": "uuid",
    "full_name": "Мария Смирнова",
    "username": "maria_s",
    "role": "assistant",
    "joined_at": "2026-02-01T09:00:00Z"
  }
]
```

**Ошибки:**
- `401` — нет токена или токен невалиден
- `403` — пользователь не является членом workspace
- `404` — workspace не найден

---

## Frontend

### API-функция

```ts
// src/api/workspaces.ts

interface UsersFilters {
  role?: 'workspace_admin' | 'assistant' | 'client'
  search?: string
}

export function createWorkspaceUsersQuery(workspaceId: string, filters: UsersFilters) {
  return createQuery({
    queryKey: ['workspaces', workspaceId, 'users', filters],
    queryFn: () =>
      apiClient.get(`/workspaces/${workspaceId}/users`, { params: filters }),
  })
}
```

### Экран: Users List

**Компоненты:**
- Поисковая строка — дебаунс 300 мс, обновляет параметр `search`
- Чипы ролей: Все / Админ / Ассистент / Клиент — устанавливают параметр `role` (или убирают его для "Все")
- Счётчик — `{data.length} пользователей`
- Список — каждый элемент: аватар с инициалами, `full_name`, `role`, цветной badge роли

**Цвета badge по роли:**

| Роль               | Фон       | Текст     |
|--------------------|-----------|-----------|
| `workspace_admin`  | `#dcfce7` | `#16a34a` |
| `assistant`        | `#FEF3C7` | `#D97706` |
| `client`           | secondary | secondary-foreground |

**Состояния:**
- Загрузка: скелетон-список
- Пустой результат при фильтрах: "Ничего не найдено"
- Пустой workspace: "Участников пока нет"

### Query key

```ts
['workspaces', workspaceId, 'users', { role?, search? }]
```

При изменении фильтров query-key меняется — TanStack Query автоматически перезапрашивает.

---

## Критерии готовности

### Backend
- [ ] `GET /workspaces/{id}/users` возвращает список активных участников
- [ ] Фильтр `?role=` работает для всех трёх ролей
- [ ] Фильтр `?search=` ищет по `full_name` и `username` (case-insensitive)
- [ ] Без фильтров возвращает всех активных участников
- [ ] Доступен всем ролям (не только admin)
- [ ] `super_admin` получает доступ без членства

### Frontend
- [ ] Чипы ролей переключают фильтр, активный чип выделен
- [ ] Поисковая строка с дебаунсом отправляет `?search=`
- [ ] Счётчик отражает количество в текущей выборке
- [ ] Цвета badge соответствуют роли
- [ ] Скелетон отображается во время загрузки
- [ ] Пустые состояния обработаны
